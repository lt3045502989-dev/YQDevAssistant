"""
Pytest fixtures for YQ Dev Assistant tests.

Fixtures are test dependencies. Instead of creating a ConfigManager
in every test, define a fixture once. pytest injects it into any
test that asks for it by parameter name.
"""

import json
from pathlib import Path

import pytest

from src.core.event_bus import EventBus
from src.core.config_manager import ConfigManager
from src.core.log_manager import LogManager
from src.core.module_manager import ModuleManager
from src.core.module_base import BaseModule, ModuleResult, ModuleInfo


# ── Temporary Files ────────────────────────────────────────


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """
    Create a temporary config directory with default.json and schema.json.

    Uses pytest's tmp_path fixture which:
    - Creates a unique temp directory
    - Deletes it after the test
    - No cleanup code needed
    """
    config_dir = tmp_path / ".yqa"
    config_dir.mkdir()

    # Copy our real config files as defaults
    defaults_src = Path("config/default.json")
    schema_src = Path("config/schema.json")

    defaults_dest = tmp_path / "default.json"
    schema_dest = tmp_path / "schema.json"

    defaults_dest.write_text(defaults_src.read_text("utf-8"), "utf-8")
    schema_dest.write_text(schema_src.read_text("utf-8"), "utf-8")

    return config_dir


# ── Core Components ────────────────────────────────────────


@pytest.fixture
def config_manager(tmp_config_dir: Path, tmp_path: Path) -> ConfigManager:
    """
    A ConfigManager pointed at a temporary directory.

    Uses the real default.json and schema.json from config/.
    """
    return ConfigManager(
        config_dir=str(tmp_config_dir),
        defaults_file=str(tmp_path / "default.json"),
        schema_file=str(tmp_path / "schema.json"),
    )


@pytest.fixture
def event_bus() -> EventBus:
    """
    A clean EventBus with no subscribers.

    Each test gets a fresh, empty EventBus.
    """
    return EventBus()


@pytest.fixture
def log_manager(tmp_path: Path) -> LogManager:
    """
    A LogManager writing to a temp directory.

    File logging goes to the temp dir (auto-cleaned).
    Console logging is disabled to keep test output clean.
    """
    log_dir = tmp_path / "logs"
    return LogManager(log_dir=str(log_dir), console=False)


# ── Dummy Module for Testing ───────────────────────────────


class DummyTestModule(BaseModule):
    """
    A minimal module for testing ModuleManager.

    Has both check() and execute() implemented.
    """

    info = ModuleInfo(
        name="dummy_test",
        version="0.1.0-test",
        description="A minimal module for testing",
        category="test",
        icon="🧪",
    )

    def check(self) -> ModuleResult:
        return ModuleResult.ok(self.info.name, {"status": "ok"})

    def execute(self, **kwargs) -> ModuleResult:
        return ModuleResult.ok(
            self.info.name,
            {"executed": True, "args": kwargs},
        )


class FailingModule(BaseModule):
    """
    A module whose check() always fails.
    Used to test error handling in ModuleManager.
    """

    info = ModuleInfo(
        name="failing_test",
        version="0.1.0-test",
        description="A module that always fails check()",
        category="test",
        icon="💥",
    )

    def check(self) -> ModuleResult:
        return ModuleResult.fail(self.info.name, ["Simulated failure"])


class CrashingModule(BaseModule):
    """
    A module whose check() raises an exception.
    Used to test exception handling in ModuleManager.
    """

    info = ModuleInfo(
        name="crashing_test",
        version="0.1.0-test",
        description="A module whose check() always crashes",
        category="test",
        icon="💀",
    )

    def check(self) -> ModuleResult:
        raise RuntimeError("Simulated crash!")
