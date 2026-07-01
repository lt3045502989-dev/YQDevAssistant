"""
YQ Dev Assistant — Configuration Manager.

Centralized configuration management with:
- JSON Schema validation
- Default + user override merging
- Dot-notation key access ("services.github.user")
- Auto-save on changes

Resolution order (lowest priority first):
    1. config/default.json   — shipped with the app, never modified by users
    2. ~/.yqa/config.json   — user overrides, created on first save
    3. (Future) Environment variables — YQA_SECTION_KEY

This is the same pattern VS Code uses:
    defaultSettings.json → settings.json → workspace settings

Design principles:
    1. FAIL SAFE: If validation fails, fall back to defaults + log warnings.
       Never crash because of a bad config file.
    2. IMMUTABLE DEFAULTS: config/default.json is read-only.
       Users override it; they don't edit it.
    3. DOT NOTATION: "services.proxy.enabled" is easier to read
       and type than config["services"]["proxy"]["enabled"].
"""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.core.exceptions import ConfigError
from src.utils.constants import DEFAULT_CONFIG_DIR

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages application configuration with JSON Schema validation.

    Usage:
        >>> cm = ConfigManager()
        >>> cm.load()
        >>> cm.get("services.github.user")
        'lt3045502989-dev'
        >>> cm.set("app.log_level", "DEBUG")
        >>> cm.reset()  # Restore all defaults
    """

    def __init__(
        self,
        config_dir: str | Path = DEFAULT_CONFIG_DIR,
        defaults_file: str | Path = "config/default.json",
        schema_file: str | Path = "config/schema.json",
    ) -> None:
        """
        Initialize ConfigManager.

        Does NOT create any files — they are created on first save().
        This allows the app to start even if config directories don't exist yet.

        Args:
            config_dir: Where user config lives (e.g., ~/.yqa/).
            defaults_file: Path to the shipped default config.
            schema_file: Path to the JSON Schema for validation.
        """
        self._config_dir = Path(config_dir).expanduser().resolve()
        self._defaults_file = Path(defaults_file)
        self._schema_file = Path(schema_file)
        self._user_config_path = self._config_dir / "config.json"

        # Lazy-loaded caches
        self._defaults: dict[str, Any] | None = None
        self._merged: dict[str, Any] | None = None
        self._schema: dict[str, Any] | None = None

    # ── Public API ─────────────────────────────────────

    def load(self) -> dict[str, Any]:
        """
        Load the full merged configuration.

        Merges defaults with user overrides, validates the result,
        and caches it for subsequent calls.

        Returns:
            Merged configuration dictionary.

        Raises:
            ConfigError: If the default config or schema file is missing.
        """
        if self._merged is not None:
            return deepcopy(self._merged)

        # Load base layers
        defaults = self._load_defaults()
        user = self._load_user_config()

        # Merge: user overrides defaults
        merged = deepcopy(defaults)
        self._deep_merge(merged, user)

        # Validate
        schema = self._load_schema()
        errors = self.validate(merged)
        if errors:
            logger.warning(
                "Config validation found %d issue(s). Using defaults + valid overrides.",
                len(errors),
            )
            for error in errors:
                logger.warning("  Config issue: %s", error)

        self._merged = merged
        return deepcopy(merged)

    def save(self, config: dict[str, Any]) -> None:
        """
        Validate and save the user configuration.

        Creates ~/.yqa/ and config.json if they don't exist.

        Args:
            config: Full or partial configuration to save.

        Raises:
            ConfigError: If validation fails.
        """
        # Validate first — never save invalid config
        errors = self.validate(config)
        if errors:
            raise ConfigError(
                f"Configuration validation failed with {len(errors)} issue(s)",
                details={"errors": errors},
            )

        # Ensure directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # Write atomically: write to temp file, then rename
        import tempfile

        fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix="yqa_config_", dir=str(self._config_dir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(self._user_config_path))
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Invalidate cache so next load() picks up the new config
        self._invalidate_cache()
        logger.info("Configuration saved to %s", self._user_config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value using dot-notation.

        Examples:
            >>> cm.get("app.name")
            'YQDevAssistant'
            >>> cm.get("services.proxy.port", 7897)
            7897

        Args:
            key: Dot-separated path (e.g., "app.log_level").
            default: Value to return if the key doesn't exist.

        Returns:
            The config value, or `default` if not found.
        """
        config = self.load()
        parts = key.split(".")
        current: Any = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def set(self, key: str, value: Any) -> None:
        """
        Set a config value using dot-notation and auto-save.

        This modifies the IN-MEMORY merged config AND persists
        the user config file.

        Examples:
            >>> cm.set("app.log_level", "DEBUG")
            >>> cm.set("modules.health.enabled", False)

        Args:
            key: Dot-separated path.
            value: New value to set.

        Raises:
            ConfigError: If the key path is invalid.
        """
        config = self.load()
        parts = key.split(".")
        current: Any = config

        # Navigate to the parent dict
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            if not isinstance(current, dict):
                raise ConfigError(
                    f"Cannot set '{key}': '{part}' is not a dictionary"
                )

        # Set the value
        current[parts[-1]] = value

        # Validate and save
        self.save(config)

    def reload(self) -> None:
        """
        Force re-reading of config files.

        Useful when you suspect files have changed on disk.
        Clears the in-memory cache so the next load() re-reads from disk.
        """
        self._invalidate_cache()
        logger.info("Configuration cache invalidated. Will reload on next access.")

    def reset(self) -> None:
        """
        Delete user config and restore all defaults.

        This removes ~/.yqa/config.json if it exists.
        The next load() will return only defaults.
        """
        if self._user_config_path.exists():
            self._user_config_path.unlink()
            logger.info("User configuration deleted: %s", self._user_config_path)
        self._invalidate_cache()

    def validate(self, config: dict[str, Any]) -> list[str]:
        """
        Validate a config dictionary against the JSON Schema.

        Args:
            config: Configuration to validate.

        Returns:
            List of error messages. Empty list = valid.
        """
        schema = self._load_schema()
        try:
            import jsonschema

            validator = jsonschema.Draft202012Validator(schema)
            errors = list(validator.iter_errors(config))
            return [str(e.message) for e in errors]
        except ImportError:
            # If jsonschema is not installed, skip validation
            # (should not happen since it's in requirements.txt)
            logger.warning("jsonschema not installed — skipping config validation")
            return []

    # ── Properties ─────────────────────────────────────

    @property
    def defaults(self) -> dict[str, Any]:
        """Read-only default configuration."""
        return deepcopy(self._load_defaults())

    @property
    def config_path(self) -> Path:
        """Path to the user config file."""
        return self._user_config_path

    # ── Internal Methods ───────────────────────────────

    def _load_defaults(self) -> dict[str, Any]:
        """Load the shipped default configuration."""
        if self._defaults is not None:
            return self._defaults

        if not self._defaults_file.exists():
            raise ConfigError(
                f"Default configuration file not found: {self._defaults_file}"
            )

        self._defaults = self._read_json(self._defaults_file)
        logger.debug("Loaded defaults from %s", self._defaults_file)
        return self._defaults

    def _load_user_config(self) -> dict[str, Any]:
        """Load the user's override configuration."""
        if not self._user_config_path.exists():
            logger.debug("No user config found at %s", self._user_config_path)
            return {}
        return self._read_json(self._user_config_path)

    def _load_schema(self) -> dict[str, Any]:
        """Load the JSON Schema for validation."""
        if self._schema is not None:
            return self._schema

        if not self._schema_file.exists():
            raise ConfigError(
                f"Config schema file not found: {self._schema_file}"
            )

        self._schema = self._read_json(self._schema_file)
        return self._schema

    def _invalidate_cache(self) -> None:
        """Clear cached config so next load() re-reads from disk."""
        self._merged = None
        self._defaults = None
        self._schema = None

    # ── Static Helpers ─────────────────────────────────

    @staticmethod
    def _read_json(path: str | Path) -> dict[str, Any]:
        """Read and parse a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """
        Recursively merge override into base (in-place).

        dict values are merged recursively.
        Non-dict values from override replace base values.
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)

    def __repr__(self) -> str:
        return f"ConfigManager(config_dir={self._config_dir})"
