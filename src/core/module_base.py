"""
YQ Dev Assistant — Base Module Framework.

This module defines the contract that EVERY functional module must follow.
Think of it as the "constitution" of the project:
    - BaseModule: what every module MUST implement
    - ModuleResult: how every module reports its results
    - ModuleInfo: metadata about each module

Design principles:
    1. check() vs execute() → CQRS (Command Query Responsibility Segregation)
       - check() is a QUERY: read-only, safe, repeatable, no side effects
       - execute() is a COMMAND: may change state, may have side effects

    2. ModuleResult uses Generic[T] for type-safe data
       - Health module returns ModuleResult[HealthReport]
       - Backup module returns ModuleResult[list[str]]

    3. Factory methods (ok/fail) over direct construction
       - ModuleResult.ok(...) reads like English
       - ModuleResult(True, ...) requires remembering argument order
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, TypeVar, Any, TYPE_CHECKING

# TYPE_CHECKING is True only during static analysis (mypy, pylance).
# At runtime, it's False. This prevents circular imports.
if TYPE_CHECKING:
    from src.core.event_bus import EventBus

T = TypeVar("T")


# ── ModuleResult ───────────────────────────────────────────


@dataclass
class ModuleResult(Generic[T]):
    """
    Standard result from any module operation (check or execute).

    Generic over T: the type of the data field.
    - Health module: ModuleResult[HealthReport]
    - Backup module: ModuleResult[list[str]]

    Fields:
        success: True if the operation completed without fatal errors.
        module_name: Which module produced this result (for traceability).
        data: The operation's output. Type depends on the module.
        errors: Fatal problems that prevented completion.
        warnings: Non-fatal issues (things to know about, but not broken).
        duration_ms: How long the operation took (auto-set by ModuleManager).
        timestamp: When the result was created (UTC).

    Use the factory methods, not the constructor:
        ModuleResult.ok("health", report)
        ModuleResult.fail("health", ["Git not found"])
    """

    success: bool
    module_name: str
    data: T | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Convenience Properties ─────────────────────────

    @property
    def has_errors(self) -> bool:
        """True if there are any errors (even if success=True)."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """True if there are any warnings."""
        return len(self.warnings) > 0

    @property
    def is_ok(self) -> bool:
        """True if successful AND no errors. The strictest check."""
        return self.success and not self.has_errors

    # ── Factory Methods ────────────────────────────────

    @classmethod
    def ok(
        cls, module_name: str, data: T, warnings: list[str] | None = None
    ) -> "ModuleResult[T]":
        """
        Create a successful result.

        Example:
            >>> ModuleResult.ok("health", {"score": 95})
            ModuleResult(success=True, module_name='health', data={'score': 95}, ...)
        """
        return cls(
            success=True,
            module_name=module_name,
            data=data,
            warnings=warnings or [],
        )

    @classmethod
    def fail(
        cls,
        module_name: str,
        errors: list[str],
        warnings: list[str] | None = None,
    ) -> "ModuleResult[None]":
        """
        Create a failed result.

        Example:
            >>> ModuleResult.fail("health", ["Git not installed"])
            ModuleResult(success=False, module_name='health', data=None, errors=['Git not installed'], ...)
        """
        return cls(
            success=False,
            module_name=module_name,
            data=None,
            errors=errors,
            warnings=warnings or [],
        )


# ── ModuleInfo ─────────────────────────────────────────────


@dataclass
class ModuleInfo:
    """
    Metadata about a module. Pure data — no behavior.

    Each module class defines this at the class level:
        class HealthModule(BaseModule):
            info = ModuleInfo(
                name="health",
                version="0.1.0",
                description="Check development environment health",
                category="maintenance",
                icon="🩺",
            )

    Fields:
        name: Unique identifier. Lowercase, alphanumeric + underscore.
        version: Semantic version (e.g., "0.1.0").
        description: One-line summary of what the module does.
        author: Who maintains this module.
        enabled: Whether this module is active (can be toggled in settings).
        icon: Emoji or icon name for UI display.
        category: Grouping label (e.g., "maintenance", "tools", "automation").
    """

    name: str
    version: str
    description: str
    author: str = "YQDevAssistant"
    enabled: bool = True
    icon: str = "📦"
    category: str = "general"


# ── BaseModule ─────────────────────────────────────────────


class BaseModule(ABC):
    """
    Abstract base class for all functional modules.

    Every module in YQ Dev Assistant must:
    1. Inherit from BaseModule
    2. Define `info` as a class-level ModuleInfo
    3. Implement `check()` → read-only diagnostic
    4. Optionally override `execute()` → action with side effects

    Lifecycle (managed by ModuleManager):
        discover → register → instantiate → configure → check/execute → unregister

    Example minimal module:
        ```python
        class HelloModule(BaseModule):
            info = ModuleInfo(
                name="hello",
                version="0.1.0",
                description="A friendly greeting module",
            )

            def check(self) -> ModuleResult:
                return ModuleResult.ok(self.info.name, {"message": "Hello!"})
        ```
    """

    # Subclasses MUST override this. Python will complain at import time
    # if a subclass forgets to define `info`.
    info: ModuleInfo

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        event_bus: "EventBus | None" = None,
    ) -> None:
        """
        Initialize the module.

        Args:
            config: Module-specific configuration (from ConfigManager).
            event_bus: Shared event bus for inter-module communication.
        """
        self.config = config or {}
        self.event_bus = event_bus

    # ── Abstract Methods (MUST override) ──────────────

    @abstractmethod
    def check(self) -> ModuleResult:
        """
        Perform a read-only diagnostic.

        Rules:
        - MUST NOT modify any files, configs, or state
        - MUST be safe to run at any time
        - MUST be reasonably fast (no long-running operations)
        - MUST return a ModuleResult (even if there's nothing to report)

        Returns:
            ModuleResult with diagnostic data in the `data` field.
        """
        ...

    # ── Optional Methods (MAY override) ───────────────

    def execute(self, **kwargs: Any) -> ModuleResult:
        """
        Perform an action. May have side effects (create files, make API calls, etc.).

        Default behavior: return a failure saying this module doesn't support execute().
        Override this if your module has actionable operations.

        Args:
            **kwargs: Module-specific arguments. Document these in your module.

        Returns:
            ModuleResult with operation results.
        """
        return ModuleResult.fail(
            self.info.name,
            [f"Module '{self.info.name}' does not support execute()"],
        )

    def configure(self, config: dict[str, Any]) -> None:
        """
        Accept new configuration.

        Called by ModuleManager when the user changes config.
        The default implementation merges the new config into self.config.
        Override if your module needs special config handling.

        Args:
            config: New configuration values (partial update).
        """
        self.config = {**self.config, **config}

    def get_status(self) -> dict[str, Any]:
        """
        Return a summary of the module's current state.

        Used by the CLI (`yqa status`) and the GUI status bar.
        Override to add module-specific status information.

        Returns:
            Dict with at least: name, version, enabled.
        """
        return {
            "name": self.info.name,
            "version": self.info.version,
            "enabled": self.info.enabled,
            "category": self.info.category,
            "icon": self.info.icon,
        }
