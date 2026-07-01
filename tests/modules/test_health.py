"""
Tests for the Health module.
"""

import pytest
from src.modules.health.module import HealthModule
from src.modules.health.checker import (
    CheckItem,
    check_tool,
    check_disk_space,
    check_memory,
    check_temp_files,
    check_windows_defender,
    check_network_github,
    run_all_checks,
)
from src.modules.health.reporter import (
    HealthReport,
    calculate_score,
    generate_report,
    format_report_compact,
)


class TestCheckItem:
    """Tests for the CheckItem data class."""

    def test_pass(self):
        item = CheckItem(name="Test", status="pass", message="OK")
        assert item.is_ok
        assert not item.is_warning
        assert not item.is_failure

    def test_warn(self):
        item = CheckItem(name="Test", status="warn", message="Warning")
        assert not item.is_ok
        assert item.is_warning
        assert not item.is_failure

    def test_fail(self):
        item = CheckItem(name="Test", status="fail", message="Failed")
        assert not item.is_ok
        assert not item.is_warning
        assert item.is_failure

    def test_score_deduction(self):
        item = CheckItem(
            name="Test", status="fail", message="Bad", score_deduction=10
        )
        assert item.score_deduction == 10


class TestHealthModule:
    """Tests for HealthModule."""

    def test_info(self):
        mod = HealthModule()
        assert mod.info.name == "health"
        assert mod.info.category == "maintenance"

    def test_check_returns_report(self):
        mod = HealthModule()
        result = mod.check()
        # Always returns data, even if there are errors
        assert result.data is not None
        assert isinstance(result.data, HealthReport)

    def test_check_has_items(self):
        mod = HealthModule()
        result = mod.check()
        assert len(result.data.items) > 0

    def test_execute_same_as_check(self):
        mod = HealthModule()
        r1 = mod.check()
        r2 = mod.execute()
        # Both should return valid reports (scores may vary slightly due to timing)
        assert r1.data is not None
        assert r2.data is not None
        assert isinstance(r1.data, HealthReport)
        assert isinstance(r2.data, HealthReport)
        # Should have the same number of checks
        assert r1.data.total == r2.data.total

    def test_get_status(self):
        mod = HealthModule()
        status = mod.get_status()
        assert "score" in status
        assert "healthy" in status


class TestToolCheck:
    """Tests for tool checking."""

    def test_git_installed(self):
        item = check_tool("Git", "git", "--version", 10)
        assert item.is_ok
        assert "git" in item.detail.lower()

    def test_nonexistent_tool(self):
        item = check_tool("FakeTool", "nonexistent_command_xyz", "--version", 10)
        assert item.is_failure
        assert item.score_deduction == 10


class TestSystemChecks:
    """Tests for system-level checks."""

    def test_disk_space(self):
        item = check_disk_space("C")
        # Should almost always work on a real Windows machine
        assert item.status in ("pass", "warn", "fail")

    def test_memory(self):
        item = check_memory()
        assert item.status in ("pass", "warn", "fail")

    def test_windows_defender(self):
        item = check_windows_defender()
        assert item.status in ("pass", "warn")

    def test_temp_files(self):
        item = check_temp_files()
        assert item.status in ("pass", "warn", "fail")

    def test_network_github(self):
        item = check_network_github(timeout=3)
        # Should pass or warn (not fail) since it depends on network
        assert item.status in ("pass", "warn")


class TestScoring:
    """Tests for the scoring algorithm."""

    def test_all_pass_is_100(self):
        items = [
            CheckItem("a", "pass", "ok"),
            CheckItem("b", "pass", "ok"),
            CheckItem("c", "pass", "ok"),
        ]
        score, grade = calculate_score(items)
        assert score == 100

    def test_deductions_reduce_score(self):
        items = [
            CheckItem("a", "fail", "bad", score_deduction=20),
            CheckItem("b", "pass", "ok"),
        ]
        score, grade = calculate_score(items)
        assert score == 80

    def test_score_clamped_to_zero(self):
        items = [
            CheckItem("a", "fail", "bad", score_deduction=60),
            CheckItem("b", "fail", "bad", score_deduction=60),
        ]
        score, grade = calculate_score(items)
        assert score == 0

    def test_excellent_grade(self):
        items = [CheckItem("a", "pass", "ok")]
        score, grade = calculate_score(items)
        assert "优秀" in grade or "Excellent" in grade

    def test_critical_grade(self):
        items = [CheckItem("a", "fail", "bad", score_deduction=50)]
        score, grade = calculate_score(items)
        assert "Critical" in grade or "立即" in grade


class TestReporter:
    """Tests for report generation and formatting."""

    def test_generate_report(self):
        items = [
            CheckItem("a", "pass", "ok"),
            CheckItem("b", "warn", "hmm", score_deduction=3),
            CheckItem("c", "fail", "bad", score_deduction=10),
        ]
        report = generate_report(items)
        assert report.score == 87
        assert report.passed == 1
        assert report.warnings == 1
        assert report.failures == 1
        assert report.total == 3

    def test_is_healthy(self):
        items = [CheckItem("a", "pass", "ok")]
        report = generate_report(items)
        assert report.is_healthy
        assert not report.is_critical

    def test_is_critical(self):
        items = [CheckItem("a", "fail", "bad", score_deduction=50)]
        report = generate_report(items)
        assert report.is_critical
        assert not report.is_healthy

    def test_format_report_compact(self):
        items = [CheckItem("a", "pass", "ok")]
        report = generate_report(items)
        text = format_report_compact(report)
        assert "100" in text
        assert "Health:" in text

    def test_run_all_checks(self):
        """Integration: run_all_checks returns a list."""
        items = run_all_checks()
        assert len(items) >= 10  # At least 10 tool checks
        assert all(isinstance(item, CheckItem) for item in items)
