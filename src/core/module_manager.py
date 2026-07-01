"""
YQ Dev Assistant — Module Manager.

The orchestrator that discovers, registers, and manages module lifecycle.
This is the bridge between the framework (core/) and the functionality (modules/).

Design principles:
    1. LAZY LOADING: Modules are discovered eagerly (fast: just scanning directories),
       but instantiated lazily (slow: importing and running Python code).
       This keeps startup fast even with many modules.

    2. LIFECYCLE MANAGEMENT:
       discover → register → instantiate → configure → check/execute → unregister

    3. DEPENDENCY INJECTION: ModuleManager creates modules and passes them
       the shared infrastructure (EventBus, ConfigManager). Modules don't
       create these themselves — they receive them.

    4. THREAD SAFETY: get_module() uses a lock to prevent race conditions
       during lazy instantiation.

    5. TIMING: Every check() and execute() call is automatically timed.
       The duration is stored in ModuleResult.duration_ms.

Usage:
    >>> mm = ModuleManager(event_bus=eb, config_manager=cm)
    >>> mm.discover()
    ['health', 'backup']
    >>> result = mm.run_check("health")
    >>> print(result.is_ok)
    True
"""

import importlib
import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any, TYPE_CHECKING

from src.core.exceptions import ModuleError, ModuleNotFoundError
from src.core.module_base import BaseModule, ModuleResult, ModuleInfo

if TYPE_CHECKING:
    from src.core.config_manager import ConfigManager
    from src.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class ModuleManager:
    """
    Discovers, registers, and manages module lifecycle.

    Modules are loaded from src/modules/ by default. Each subdirectory
    containing a module.py with a BaseModule subclass is a module.

    Lifecycle:
        1. discover()     → Scan directories, find available modules
        2. register()     → Register a module class (optional; discover calls this)
        3. get_module()   → Lazy instantiation on first access
        4. run_check()    → Execute the module's check() method
        5. run_execute()  → Execute the module's execute() method
        6. unregister()   → Remove a module from the registry
    """

    def __init__(
        self,
        modules_dir: str | Path = "src/modules",
        config_manager: "ConfigManager | None" = None,
        event_bus: "EventBus | None" = None,
    ) -> None:
        """
        Initialize the ModuleManager.

        Args:
            modules_dir: Directory to scan for modules.
            config_manager: Shared ConfigManager (injected).
            event_bus: Shared EventBus (injected).
        """
        self._modules_dir = Path(modules_dir)
        self._config_manager = config_manager
        self._event_bus = event_bus

        # Registered module CLASSES (not instances): name → class
        self._registry: dict[str, type[BaseModule]] = {}

        # Instantiated module instances: name → instance
        # Only populated when get_module() is called (lazy loading)
        self._instances: dict[str, BaseModule] = {}

        # Protects _instances during lazy instantiation
        self._instance_lock = Lock()

    # ── Discovery ──────────────────────────────────────

    def discover(self) -> list[str]:
        """
        Scan the modules directory for available modules.

        A valid module directory must contain a module.py with at least one
        class that inherits from BaseModule.

        This is fast: it only imports the Python file and checks for
        BaseModule subclasses. No instances are created.

        Returns:
            List of discovered module names (sorted alphabetically).

        Raises:
            ModuleError: If the modules directory doesn't exist.
        """
        if not self._modules_dir.exists():
            raise ModuleError(
                f"Modules directory not found: {self._modules_dir}",
                details={"modules_dir": str(self._modules_dir)},
            )

        discovered = []

        for entry in sorted(self._modules_dir.iterdir()):
            # Skip files, hidden dirs, and dirs without module.py
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue

            module_file = entry / "module.py"
            if not module_file.exists():
                logger.debug(
                    "Skipping '%s': no module.py found", entry.name
                )
                continue

            # Try to import the module and find BaseModule subclasses
            try:
                module_classes = self._find_module_classes(entry.name, module_file)
                if not module_classes:
                    logger.debug(
                        "Skipping '%s': no BaseModule subclass found", entry.name
                    )
                    continue

                for cls in module_classes:
                    self.register(cls)
                    discovered.append(cls.info.name)

            except Exception as e:
                logger.warning(
                    "Failed to load module from '%s': %s", entry.name, e
                )
                continue

        logger.info(
            "Discovered %d module(s): %s",
            len(discovered),
            ", ".join(discovered) if discovered else "(none)",
        )
        return discovered

    # ── Registration ───────────────────────────────────

    def register(
        self,
        module_class: type[BaseModule],
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a module class.

        Does NOT instantiate it (lazy loading).
        The module won't be created until get_module() is called.

        Args:
            module_class: A class inheriting from BaseModule.
            config: Optional module-specific configuration.

        Raises:
            ModuleError: If the class doesn't have a valid ModuleInfo.
            TypeError: If module_class is not a BaseModule subclass.
        """
        if not issubclass(module_class, BaseModule):
            raise TypeError(
                f"Expected a BaseModule subclass, got {module_class.__name__}"
            )

        # Validate that the class has a proper info attribute
        info = getattr(module_class, "info", None)
        if info is None or not isinstance(info, ModuleInfo):
            raise ModuleError(
                f"Module class '{module_class.__name__}' is missing a valid "
                f"'info' attribute. Define: info = ModuleInfo(name='...', ...)"
            )

        name = info.name

        if name in self._registry:
            existing = self._registry[name]
            logger.warning(
                "Module '%s' is already registered (%s). Replacing with %s.",
                name,
                existing.__name__,
                module_class.__name__,
            )

        self._registry[name] = module_class
        logger.info("Registered module: %s (%s)", name, module_class.__name__)

        # Publish event for other modules to react
        if self._event_bus:
            self._event_bus.publish(
                "module:registered",
                {
                    "name": name,
                    "version": info.version,
                    "description": info.description,
                },
            )

    # ── Access ─────────────────────────────────────────

    def get_module(self, name: str) -> BaseModule:
        """
        Get a module instance by name (lazy instantiation).

        The first call for a given module creates the instance.
        Subsequent calls return the cached instance.

        Args:
            name: Module name (e.g., "health").

        Returns:
            The module instance.

        Raises:
            ModuleNotFoundError: If no module with this name is registered.
        """
        # Fast path: already instantiated
        if name in self._instances:
            return self._instances[name]

        # Slow path: need to instantiate
        with self._instance_lock:
            # Double-check: another thread might have instantiated
            # while we were waiting for the lock
            if name in self._instances:
                return self._instances[name]

            if name not in self._registry:
                raise ModuleNotFoundError(
                    f"Module '{name}' not found. Available modules: "
                    f"{list(self._registry.keys())}"
                )

            module_class = self._registry[name]

            # Get module-specific config
            module_config = {}
            if self._config_manager:
                module_config = self._config_manager.get(
                    f"modules.{name}", {}
                )

            # Instantiate with dependency injection
            try:
                instance = module_class(
                    config=module_config,
                    event_bus=self._event_bus,
                )
            except Exception as e:
                raise ModuleError(
                    f"Failed to instantiate module '{name}': {e}",
                    details={"module_name": name, "error": str(e)},
                ) from e

            self._instances[name] = instance
            logger.info(
                "Module '%s' instantiated (lazy load)", name
            )

            # Publish lifecycle event
            if self._event_bus:
                self._event_bus.publish(
                    "module:instantiated",
                    {"name": name, "version": instance.info.version},
                )

            return instance

    def get_all_modules(self) -> dict[str, BaseModule]:
        """
        Get all registered module instances.

        Calls get_module() for every registered module,
        triggering lazy instantiation for any that haven't been loaded yet.

        Returns:
            Dict mapping module name → instance.
        """
        return {name: self.get_module(name) for name in self._registry}

    # ── Execution ──────────────────────────────────────

    def run_check(self, name: str) -> ModuleResult:
        """
        Run the check() method on a module.

        Automatically times the execution and fills in duration_ms.

        Args:
            name: Module name.

        Returns:
            ModuleResult from the module's check() method.

        Raises:
            ModuleNotFoundError: If the module doesn't exist.
        """
        module = self.get_module(name)
        logger.info("Running check on module '%s'...", name)

        if self._event_bus:
            self._event_bus.publish(
                "module:check_started", {"name": name}
            )

        start = time.perf_counter()
        try:
            result = module.check()
        except Exception as e:
            logger.exception("Module '%s' check() raised an exception", name)
            result = ModuleResult.fail(
                name, [f"check() raised {type(e).__name__}: {e}"]
            )

        result.duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Module '%s' check %s (%.0fms)",
            name,
            "passed" if result.is_ok else "failed",
            result.duration_ms,
        )

        if self._event_bus:
            event_name = (
                "module:check_completed" if result.is_ok else "module:check_failed"
            )
            self._event_bus.publish(
                event_name,
                {
                    "name": name,
                    "result": result,
                    "duration_ms": result.duration_ms,
                },
            )

        return result

    def run_execute(self, name: str, **kwargs: Any) -> ModuleResult:
        """
        Run the execute() method on a module.

        Automatically times the execution.

        Args:
            name: Module name.
            **kwargs: Passed to the module's execute() method.

        Returns:
            ModuleResult from the module's execute() method.

        Raises:
            ModuleNotFoundError: If the module doesn't exist.
        """
        module = self.get_module(name)
        logger.info("Running execute on module '%s'...", name)

        if self._event_bus:
            self._event_bus.publish(
                "module:execute_started", {"name": name}
            )

        start = time.perf_counter()
        try:
            result = module.execute(**kwargs)
        except Exception as e:
            logger.exception("Module '%s' execute() raised an exception", name)
            result = ModuleResult.fail(
                name, [f"execute() raised {type(e).__name__}: {e}"]
            )

        result.duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Module '%s' execute %s (%.0fms)",
            name,
            "completed" if result.is_ok else "failed",
            result.duration_ms,
        )

        if self._event_bus:
            event_name = (
                "module:execute_completed"
                if result.is_ok
                else "module:execute_failed"
            )
            self._event_bus.publish(
                event_name,
                {
                    "name": name,
                    "result": result,
                    "duration_ms": result.duration_ms,
                },
            )

        return result

    # ── Status ─────────────────────────────────────────

    def get_status_all(self) -> dict[str, dict[str, Any]]:
        """
        Get status from all registered modules.

        Calls get_status() on each module instance.

        Returns:
            Dict mapping module name → status dict.
        """
        modules = self.get_all_modules()
        return {name: module.get_status() for name, module in modules.items()}

    # ── Cleanup ────────────────────────────────────────

    def unregister(self, name: str) -> None:
        """
        Remove a module from the registry.

        Removes both the class registration and any cached instance.

        Args:
            name: Module name to remove.

        Raises:
            ModuleNotFoundError: If no module with this name is registered.
        """
        if name not in self._registry:
            raise ModuleNotFoundError(
                f"Cannot unregister: module '{name}' not found"
            )

        del self._registry[name]
        if name in self._instances:
            del self._instances[name]

        logger.info("Module '%s' unregistered", name)

        if self._event_bus:
            self._event_bus.publish(
                "module:unregistered", {"name": name}
            )

    # ── Properties ─────────────────────────────────────

    @property
    def module_names(self) -> list[str]:
        """Names of all registered modules (sorted)."""
        return sorted(self._registry.keys())

    @property
    def loaded_modules(self) -> list[str]:
        """Names of modules that have been instantiated (lazy-loaded)."""
        return sorted(self._instances.keys())

    # ── Internal ───────────────────────────────────────

    def _find_module_classes(
        self, dir_name: str, module_file: Path
    ) -> list[type[BaseModule]]:
        """
        Import a module.py file and find all BaseModule subclasses.

        Uses importlib to dynamically load the module.
        """
        # Build the import path: src.modules.<dir_name>.module
        import_path = f"src.modules.{dir_name}.module"

        try:
            mod = importlib.import_module(import_path)
        except ImportError as e:
            logger.warning(
                "Failed to import '%s': %s", import_path, e
            )
            return []

        # Find all classes that inherit from BaseModule
        # (but are not BaseModule itself or ModuleResult/ModuleInfo)
        classes = []
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not isinstance(attr, type):
                continue
            if attr is BaseModule:
                continue
            if issubclass(attr, BaseModule):
                classes.append(attr)

        return classes

    def __repr__(self) -> str:
        return (
            f"ModuleManager(registered={len(self._registry)}, "
            f"loaded={len(self._instances)})"
        )
