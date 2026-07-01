"""
Tests for the Update module.
"""

from src.modules.update.module import UpdateModule
from src.modules.update.version_checker import (
    UpdateItem,
    check_npm_package,
    check_report_only,
    run_all_checks,
)


class TestUpdateItem:
    """Tests for UpdateItem dataclass."""

    def test_update_available(self):
        item = UpdateItem(
            name="npm",
            current_version="10.0.0",
            latest_version="11.0.0",
            update_available=True,
            update_command="npm install -g npm@latest",
            check_method="npm",
        )
        assert item.update_available
        assert item.update_command

    def test_no_update(self):
        item = UpdateItem(
            name="npm",
            current_version="11.0.0",
            latest_version="11.0.0",
            update_available=False,
            check_method="npm",
        )
        assert not item.update_available

    def test_report_only(self):
        item = UpdateItem(
            name="Git",
            current_version="2.53.0",
            check_method="report-only",
        )
        assert item.latest_version is None
        assert not item.update_available


class TestUpdateModule:
    """Tests for UpdateModule."""

    def test_info(self):
        mod = UpdateModule()
        assert mod.info.name == "update"
        assert mod.info.category == "maintenance"

    def test_check_returns_data(self):
        mod = UpdateModule()
        result = mod.check()
        assert result.data is not None
        assert "items" in result.data
        assert "updates_available" in result.data
        assert "total_checked" in result.data

    def test_check_has_items(self):
        mod = UpdateModule()
        result = mod.check()
        assert len(result.data["items"]) > 0

    def test_execute_same_as_check(self):
        mod = UpdateModule()
        r1 = mod.check()
        r2 = mod.execute()
        assert r1.data["updates_available"] == r2.data["updates_available"]

    def test_get_status(self):
        mod = UpdateModule()
        status = mod.get_status()
        assert "updates_available" in status

    def test_run_all_checks(self):
        """Integration: run_all_checks returns items."""
        items = run_all_checks()
        assert len(items) >= 9  # 3 npm + pip + 5 report-only
        assert all(isinstance(item, UpdateItem) for item in items)

    def test_npm_check_returns_item(self):
        """check_npm_package for npm itself should work."""
        item = check_npm_package("npm", "npm", "npm install -g npm@latest")
        assert isinstance(item, UpdateItem)
        assert item.name == "npm"
        assert item.check_method == "npm"

    def test_report_only_returns_item(self):
        """check_report_only for git should work."""
        item = check_report_only("Git", "git", "--version")
        assert isinstance(item, UpdateItem)
        assert item.name == "Git"
        assert item.check_method == "report-only"
        assert "git" in item.current_version.lower()
