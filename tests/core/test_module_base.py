"""
Tests for src.core.module_base — the "constitution" of the project.
"""

import pytest
from src.core.module_base import (
    BaseModule,
    ModuleResult,
    ModuleInfo,
)


class TestModuleResult:
    """Tests for the ModuleResult dataclass."""

    def test_ok_factory(self):
        """ModuleResult.ok() creates a successful result."""
        result = ModuleResult.ok("test", {"key": "value"})
        assert result.success is True
        assert result.module_name == "test"
        assert result.data == {"key": "value"}
        assert result.has_errors is False
        assert result.is_ok is True

    def test_ok_with_warnings(self):
        """ModuleResult.ok() can include warnings."""
        result = ModuleResult.ok(
            "test", {"key": "value"}, warnings=["disk space low"]
        )
        assert result.success is True
        assert result.has_warnings is True
        assert len(result.warnings) == 1
        # is_ok checks success AND no errors (warnings don't affect it)
        assert result.is_ok is True

    def test_fail_factory(self):
        """ModuleResult.fail() creates a failed result."""
        result = ModuleResult.fail("test", ["something broke"])
        assert result.success is False
        assert result.module_name == "test"
        assert result.data is None
        assert result.has_errors is True
        assert result.is_ok is False

    def test_fail_with_warnings(self):
        """ModuleResult.fail() can also include warnings."""
        result = ModuleResult.fail(
            "test", ["error 1"], warnings=["also, warning 1"]
        )
        assert result.has_errors is True
        assert result.has_warnings is True

    def test_is_ok_strict(self):
        """
        is_ok is the STRICTEST check.

        It requires BOTH:
        1. success is True
        2. no errors

        A result with success=True but errors is NOT ok.
        """
        result = ModuleResult(
            success=True,
            module_name="test",
            errors=["silent error"],
        )
        assert result.success is True  # technically "successful"
        assert result.has_errors is True  # but has errors
        assert result.is_ok is False  # so NOT ok

    def test_timestamp_auto_set(self):
        """ModuleResult auto-sets timestamp to UTC now."""
        result = ModuleResult.ok("test", {})
        assert result.timestamp is not None

    def test_default_values(self):
        """Fields have sensible defaults."""
        result = ModuleResult(success=True, module_name="test")
        assert result.data is None
        assert result.errors == []
        assert result.warnings == []
        assert result.duration_ms == 0.0

    def test_generic_type(self):
        """
        ModuleResult is generic over its data type.

        This is primarily for static type checkers (mypy, pylance).
        At runtime, the generic parameter is not enforced.
        """
        # With explicit type (for type checker)
        result: ModuleResult[dict] = ModuleResult.ok("test", {"a": 1})
        assert isinstance(result.data, dict)

        # Different data types
        str_result = ModuleResult.ok("test", "hello")
        assert isinstance(str_result.data, str)

        list_result = ModuleResult.ok("test", [1, 2, 3])
        assert isinstance(list_result.data, list)


class TestBaseModule:
    """Tests for BaseModule abstract class."""

    def test_cannot_instantiate_abstract(self):
        """
        BaseModule cannot be instantiated because it has abstract methods.

        Python enforces this at runtime.
        """
        with pytest.raises(TypeError) as exc_info:
            BaseModule()

        assert "abstract" in str(exc_info.value).lower()

    def test_concrete_subclass_must_implement_check(self):
        """
        A subclass that doesn't implement check() is also abstract.

        Python prevents instantiation.
        """

        class IncompleteModule(BaseModule):
            info = ModuleInfo(name="incomplete", version="0.1.0", description="...")

        with pytest.raises(TypeError):
            IncompleteModule()

    def test_concrete_subclass_with_check_works(self):
        """
        A subclass that implements check() can be instantiated.
        """

        class CompleteModule(BaseModule):
            info = ModuleInfo(name="complete", version="0.1.0", description="...")

            def check(self) -> ModuleResult:
                return ModuleResult.ok(self.info.name, {"ready": True})

        mod = CompleteModule()
        assert mod.info.name == "complete"

    def test_execute_default_behavior(self):
        """
        If a module doesn't override execute(), it returns a failure.

        This is the default behavior — modules must opt-in to being executable.
        """

        class CheckOnlyModule(BaseModule):
            info = ModuleInfo(name="check_only", version="0.1.0", description="...")

            def check(self) -> ModuleResult:
                return ModuleResult.ok(self.info.name, {})

        mod = CheckOnlyModule()
        result = mod.execute()
        assert result.success is False
        assert "does not support execute" in result.errors[0]

    def test_configure_merges_config(self):
        """
        configure() merges new config into existing config.

        It's a merge, not a replace — existing keys are preserved
        unless explicitly overridden.
        """

        class ConfigModule(BaseModule):
            info = ModuleInfo(name="cfg", version="0.1.0", description="...")

            def check(self) -> ModuleResult:
                return ModuleResult.ok(self.info.name, {})

        mod = ConfigModule(config={"a": 1, "b": 2})
        mod.configure({"b": 3, "c": 4})
        assert mod.config == {"a": 1, "b": 3, "c": 4}

    def test_get_status_default(self):
        """get_status() returns basic module info."""

        class StatusModule(BaseModule):
            info = ModuleInfo(
                name="status_test",
                version="0.1.0",
                description="...",
                category="test",
                icon="🔧",
            )

            def check(self) -> ModuleResult:
                return ModuleResult.ok(self.info.name, {})

        mod = StatusModule()
        status = mod.get_status()
        assert status["name"] == "status_test"
        assert status["version"] == "0.1.0"
        assert status["enabled"] is True
        assert status["category"] == "test"
        assert status["icon"] == "🔧"

    def test_module_info_defaults(self):
        """ModuleInfo has sensible defaults for optional fields."""
        info = ModuleInfo(name="min", version="1.0", description="minimal")
        assert info.author == "YQDevAssistant"
        assert info.enabled is True
        assert info.icon == "📦"
        assert info.category == "general"
