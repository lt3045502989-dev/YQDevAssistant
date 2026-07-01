"""
Health Reporter — scoring algorithm and result formatting.

The scoring model (inherited from weekly-health.sh):
    - Start at 100 points
    - Deduct for each issue found
    - ≥ 90: Excellent
    - 75-89: Good
    - 60-74: Needs attention
    - < 60: Critical

Design: the reporter is SEPARATE from the checker.
    - checker.py: produces CheckItems (raw data)
    - reporter.py: scores and formats CheckItems (presentation)

This separation means:
    - The scoring algorithm can be changed without touching check logic
    - The output format can be changed for CLI vs GUI vs JSON
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from src.modules.health.checker import CheckItem


# ── Health Report ──────────────────────────────────────────


@dataclass
class HealthReport:
    """
    Complete health check report.

    This is the data type that HealthModule.check() returns
    in ModuleResult[HealthReport].

    Attributes:
        items: All individual check results.
        score: Overall health score (0-100).
        grade: Human-readable grade ("Excellent", "Good", etc.).
        passed: Number of passing checks.
        warnings: Number of warnings.
        failures: Number of failures.
        timestamp: When the report was generated.
    """

    items: list[CheckItem] = field(default_factory=list)
    score: int = 100
    grade: str = "Unknown"
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total(self) -> int:
        """Total number of checks run."""
        return len(self.items)

    @property
    def is_healthy(self) -> bool:
        """True if the overall health is good or excellent."""
        return self.score >= 75

    @property
    def is_critical(self) -> bool:
        """True if health is critical (needs immediate attention)."""
        return self.score < 60


# ── Scoring ────────────────────────────────────────────────


def calculate_score(items: list[CheckItem]) -> tuple[int, str]:
    """
    Calculate the health score from a list of CheckItems.

    Starts at 100 and deducts based on each item's score_deduction.
    Score is clamped to [0, 100].

    Args:
        items: List of check results.

    Returns:
        Tuple of (score, grade_label).
    """
    score = 100

    for item in items:
        score -= item.score_deduction

    # Clamp to valid range
    score = max(0, min(100, score))

    # Determine grade
    if score >= 90:
        grade = "优秀 (Excellent)"
    elif score >= 75:
        grade = "良好 (Good)"
    elif score >= 60:
        grade = "需要注意 (Needs Attention)"
    else:
        grade = "需要立即处理 (Critical)"

    return score, grade


def generate_report(items: list[CheckItem]) -> HealthReport:
    """
    Generate a complete HealthReport from check results.

    Args:
        items: Results from run_all_checks().

    Returns:
        HealthReport with score, grade, and statistics.
    """
    score, grade = calculate_score(items)

    passed = sum(1 for item in items if item.is_ok)
    warnings = sum(1 for item in items if item.is_warning)
    failures = sum(1 for item in items if item.is_failure)

    return HealthReport(
        items=items,
        score=score,
        grade=grade,
        passed=passed,
        warnings=warnings,
        failures=failures,
    )


# ── Formatting ─────────────────────────────────────────────


def format_report_cli(report: HealthReport) -> str:
    """
    Format a HealthReport for CLI display.

    Args:
        report: Generated health report.

    Returns:
        Multi-line string ready for terminal output.
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append(f"  🩺 开发环境健康检查 — {report.timestamp.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")

    # Tool section
    lines.append("━━━ 开发工具 ━━━")
    tool_items = [item for item in report.items if item.name in [
        "Git", "Node.js", "npm", "pnpm", "Python", "pip",
        "Go", "VS Code", "Claude Code", "Codex CLI",
    ]]
    for item in tool_items:
        icon = _status_icon(item.status)
        detail_str = f" — {item.detail}" if item.detail else ""
        lines.append(f"  {icon} {item.name}{detail_str}")

    # Network section
    lines.append("")
    lines.append("━━━ 网络 ━━━")
    net_items = [item for item in report.items if "连接" in item.name or "GitHub" in item.name or "Google" in item.name]
    for item in net_items:
        icon = _status_icon(item.status)
        lines.append(f"  {icon} {item.message}")

    # System section
    lines.append("")
    lines.append("━━━ 系统 ━━━")
    sys_items = [item for item in report.items if item.name not in [
        "Git", "Node.js", "npm", "pnpm", "Python", "pip",
        "Go", "VS Code", "Claude Code", "Codex CLI",
    ] and "连接" not in item.name and "GitHub" not in item.name and "Google" not in item.name]
    for item in sys_items:
        icon = _status_icon(item.status)
        detail_str = f" — {item.detail}" if item.detail else ""
        lines.append(f"  {icon} {item.name}: {item.message}{detail_str}")

    # Summary
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"  评分: {report.score}/100 — {report.grade}")
    lines.append(f"  通过: {report.passed} | 警告: {report.warnings} | 失败: {report.failures}")
    lines.append("=" * 60)

    return "\n".join(lines)


def format_report_compact(report: HealthReport) -> str:
    """
    Format a HealthReport as a single compact line.

    Used for status summaries.

    Args:
        report: Generated health report.

    Returns:
        Single-line string like "Health: 92/100 (Excellent) — 14 pass, 2 warn"
    """
    return (
        f"Health: {report.score}/100 ({report.grade}) "
        f"— {report.passed} pass, {report.warnings} warn"
        + (f", {report.failures} fail" if report.failures > 0 else "")
    )


def _status_icon(status: str) -> str:
    """Map status string to icon."""
    return {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}.get(status, "[???]")
