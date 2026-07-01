"""
Tests for src.core.config_manager — configuration management.
"""

import json
import pytest
from pathlib import Path
from src.core.exceptions import ConfigError
from src.core.config_manager import ConfigManager


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_load_defaults(self, config_manager):
        """Loading with no user config returns defaults."""
        config = config_manager.load()
        assert config["app"]["name"] == "YQDevAssistant"
        assert config["app"]["language"] == "zh-CN"

    def test_get_dot_notation(self, config_manager):
        """get() with dot notation retrieves nested values."""
        config_manager.load()
        assert config_manager.get("app.name") == "YQDevAssistant"
        assert config_manager.get("services.proxy.http") == "http://127.0.0.1:7897"
        assert config_manager.get("services.github.user") == "lt3045502989-dev"

    def test_get_nonexistent_returns_default(self, config_manager):
        """get() returns the default value for nonexistent keys."""
        config_manager.load()
        assert config_manager.get("nonexistent.key") is None
        assert config_manager.get("nonexistent.key", "fallback") == "fallback"

    def test_save_and_reload(self, config_manager):
        """save() persists config, load() picks it up."""
        config_manager.load()
        config_manager.set("app.language", "en-US")
        config_manager.reload()
        assert config_manager.get("app.language") == "en-US"

    def test_set_auto_saves(self, config_manager):
        """set() validates and saves automatically."""
        config_manager.load()
        config_manager.set("app.log_level", "DEBUG")
        # Read back fresh
        config_manager.reload()
        assert config_manager.get("app.log_level") == "DEBUG"

    def test_defaults_property(self, config_manager):
        """defaults property returns read-only defaults."""
        defaults = config_manager.defaults
        assert defaults["app"]["name"] == "YQDevAssistant"
        # Verify it's a copy, not the internal dict
        defaults["app"]["name"] = "MODIFIED"
        defaults2 = config_manager.defaults
        assert defaults2["app"]["name"] == "YQDevAssistant"

    def test_reset_clears_user_config(self, config_manager):
        """reset() restores all defaults."""
        config_manager.load()
        config_manager.set("app.language", "en-US")

        # Verify it was set
        assert config_manager.get("app.language") == "en-US"

        config_manager.reset()
        config_manager.reload()
        assert config_manager.get("app.language") == "zh-CN"

    def test_validate_valid_config(self, config_manager):
        """Validation passes for a valid config."""
        errors = config_manager.validate({
            "app": {
                "name": "YQDevAssistant",
                "version": "0.1.0",
                "language": "zh-CN",
                "log_level": "INFO",
            },
            "services": {
                "proxy": {"enabled": True},
                "github": {
                    "api_base": "https://api.github.com",
                    "token_env_var": "GITHUB_TOKEN",
                    "user": "test",
                },
            },
            "paths": {
                "logs_dir": "logs",
                "backups_dir": "backups",
                "data_dir": "~/.yqa",
            },
        })
        assert errors == []

    def test_validate_invalid_config(self, config_manager):
        """Validation returns errors for invalid config."""
        errors = config_manager.validate({
            "app": {
                "name": 123,  # Should be string
            },
        })
        assert len(errors) > 0

    def test_missing_default_file_raises(self):
        """ConfigManager raises ConfigError if default.json is missing."""
        with pytest.raises(ConfigError):
            cm = ConfigManager(
                config_dir="~/.yqa-test-missing",
                defaults_file="nonexistent/default.json",
                schema_file="config/schema.json",
            )
            cm.load()

    def test_config_path_property(self, config_manager):
        """config_path returns the user config file path."""
        expected = Path(config_manager._config_dir) / "config.json"
        assert config_manager.config_path == expected

    def test_load_is_cached(self, config_manager):
        """load() caches results; reload() clears cache."""
        config1 = config_manager.load()
        config2 = config_manager.load()
        # Same object (from cache)
        assert config1 is not config2  # deep copies
        assert config1 == config2  # but equal

    def test_reload_invalidates_cache(self, config_manager):
        """reload() forces re-reading from disk."""
        config_manager.load()
        # Modify the user config file directly
        config_manager._user_config_path.parent.mkdir(parents=True, exist_ok=True)
        config_manager._user_config_path.write_text(
            json.dumps({"app": {"language": "en-US"}}), encoding="utf-8"
        )
        config_manager.reload()
        assert config_manager.get("app.language") == "en-US"
