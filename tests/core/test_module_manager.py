"""
Tests for src.core.module_manager — module lifecycle management.
"""

import pytest
from src.core.module_manager import ModuleManager
from src.core.exceptions import ModuleNotFoundError
from tests.conftest import DummyTestModule, FailingModule, CrashingModule


class TestModuleManager:
    """Tests for ModuleManager."""

    def test_register_adds_module(self, event_bus, config_manager):
        """register() adds a module class to the registry."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        assert "dummy_test" in mm.module_names

    def test_register_twice_replaces(self, event_bus, config_manager):
        """Registering the same name twice replaces the first registration."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)
        mm.register(DummyTestModule)  # Second registration
        assert mm.module_names == ["dummy_test"]

    def test_register_publishes_event(self, event_bus, config_manager):
        """Registering a module publishes a 'module:registered' event."""
        events = []
        event_bus.subscribe("module:*", lambda n, d: events.append(n))

        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        assert "module:registered" in events

    def test_get_module_lazy_loads(self, event_bus, config_manager):
        """get_module() instantiates on first call, caches on subsequent calls."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        # Before get_module: not loaded
        assert "dummy_test" not in mm.loaded_modules

        # First call: instantiate
        mod1 = mm.get_module("dummy_test")
        assert "dummy_test" in mm.loaded_modules

        # Second call: return cached instance
        mod2 = mm.get_module("dummy_test")
        assert mod1 is mod2  # Same object

    def test_get_module_unknown_raises(self, event_bus, config_manager):
        """get_module() raises ModuleNotFoundError for unknown modules."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)

        with pytest.raises(ModuleNotFoundError) as exc_info:
            mm.get_module("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_run_check_success(self, event_bus, config_manager):
        """run_check() returns the module's check() result."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        result = mm.run_check("dummy_test")
        assert result.success is True
        assert result.is_ok is True
        assert result.data == {"status": "ok"}
        assert result.duration_ms >= 0  # Timed

    def test_run_check_failure(self, event_bus, config_manager):
        """run_check() handles failing modules gracefully."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(FailingModule)

        result = mm.run_check("failing_test")
        assert result.success is False
        assert result.is_ok is False
        assert "Simulated failure" in result.errors

    def test_run_check_crash(self, event_bus, config_manager):
        """
        run_check() catches exceptions and wraps them in ModuleResult.

        A module that crashes during check() should NOT crash the
        entire application. The exception should be captured in
        the result's errors list.
        """
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(CrashingModule)

        # Should NOT raise
        result = mm.run_check("crashing_test")
        assert result.success is False
        assert len(result.errors) > 0
        assert "Simulated crash" in result.errors[0] or "RuntimeError" in result.errors[0]

    def test_run_execute_passes_kwargs(self, event_bus, config_manager):
        """run_execute() passes kwargs to the module's execute()."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        result = mm.run_execute("dummy_test", target="world", verbose=True)
        assert result.success is True
        assert result.data["args"]["target"] == "world"
        assert result.data["args"]["verbose"] is True

    def test_run_execute_without_override(self, event_bus, config_manager):
        """
        If a module doesn't override execute(), run_execute() returns failure.

        FailingModule only implements check(), not execute().
        """
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(FailingModule)

        result = mm.run_execute("failing_test")
        assert result.success is False
        assert "does not support execute" in result.errors[0]

    def test_get_all_modules(self, event_bus, config_manager):
        """get_all_modules() returns all registered module instances."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)
        mm.register(FailingModule)

        all_mods = mm.get_all_modules()
        assert len(all_mods) == 2
        assert "dummy_test" in all_mods
        assert "failing_test" in all_mods

    def test_get_status_all(self, event_bus, config_manager):
        """get_status_all() returns status dicts for all modules."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)

        statuses = mm.get_status_all()
        assert "dummy_test" in statuses
        assert statuses["dummy_test"]["name"] == "dummy_test"
        assert statuses["dummy_test"]["enabled"] is True

    def test_unregister(self, event_bus, config_manager):
        """unregister() removes a module from the registry and instances."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)
        mm.register(DummyTestModule)
        mm.get_module("dummy_test")  # Force instantiation

        assert "dummy_test" in mm.module_names
        assert "dummy_test" in mm.loaded_modules

        mm.unregister("dummy_test")

        assert "dummy_test" not in mm.module_names
        assert "dummy_test" not in mm.loaded_modules

    def test_unregister_unknown_raises(self, event_bus, config_manager):
        """unregister() raises for unknown modules."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)

        with pytest.raises(ModuleNotFoundError):
            mm.unregister("nonexistent")

    def test_discover_empty_directory(self, event_bus, config_manager, tmp_path):
        """discover() returns empty list for empty modules directory."""
        modules_dir = tmp_path / "empty_modules"
        modules_dir.mkdir()

        mm = ModuleManager(
            modules_dir=str(modules_dir),
            event_bus=event_bus,
            config_manager=config_manager,
        )

        discovered = mm.discover()
        assert discovered == []

    def test_register_wrong_type_raises(self, event_bus, config_manager):
        """register() raises TypeError if the class is not a BaseModule."""
        mm = ModuleManager(event_bus=event_bus, config_manager=config_manager)

        class NotAModule:
            pass

        with pytest.raises(TypeError):
            mm.register(NotAModule)
