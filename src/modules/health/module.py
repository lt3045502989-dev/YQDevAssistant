"""
Health Module — development environment health checks.

Checks:
    - 10 development tools (Git, Node.js, npm, pnpm, Python, pip,
      Go, VS Code, Claude Code, Codex CLI)
    - Network connectivity (GitHub, Google)
    - System status (disk space, memory, Windows Defender, temp files)

Usage:
    # CLI
    yqa check health
    yqa run health

    # Python
    python -m src.modules.health

    # Code
    from src.modules.health.module import HealthModule
    mod = HealthModule()
    result = mod.check()
"""

from src.core.module_base import BaseModule, ModuleResult, ModuleInfo
from src.modules.health.checker import run_all_checks, CheckItem
from src.modules.health.reporter import generate_report, HealthReport


class HealthModule(BaseModule):
    """
    Development environment health checker.

    check() — runs all checks (read-only, safe)
    execute() — same as check() (health checks have no side effects)
    """

    info = ModuleInfo(
        name="health",
        version="0.1.0",
        description="开发环境健康检查 — 检查工具、网络、系统状态",
        category="maintenance",
        icon="🩺",
    )

    def check(self) -> ModuleResult[HealthReport]:
        """
        Run all health checks and return a scored report.

        This is a QUERY: read-only, safe, repeatable.
        No files are modified. No side effects.

        Returns:
            ModuleResult[HealthReport] with the health report in data.
        """
        items = run_all_checks()
        report = generate_report(items)

        # Collect warnings and errors for the ModuleResult
        warnings = []
        errors = []

        for item in items:
            if item.is_warning:
                warnings.append(f"[{item.name}] {item.message}")
            elif item.is_failure:
                errors.append(f"[{item.name}] {item.message}")

        # Always include the full report in data, even if there are errors.
        # Users need to see the complete picture — not just the first error.
        if errors:
            # Manually construct to include both errors AND the report data
            return ModuleResult(
                success=False,
                module_name=self.info.name,
                data=report,
                errors=errors,
                warnings=warnings,
            )

        return ModuleResult.ok(self.info.name, report, warnings)

    def execute(self, **kwargs) -> ModuleResult[HealthReport]:
        """
        Run health checks (same as check, since health checks are always safe).

        Supports keyword arguments for filtering checks (future):
            yqa run health tools_only=true
        """
        return self.check()

    def get_status(self) -> dict:
        """
        Return current health status summary.

        Runs a quick check for the status command.
        """
        status = super().get_status()
        try:
            items = run_all_checks()
            report = generate_report(items)
            status["score"] = report.score
            status["grade"] = report.grade
            status["healthy"] = report.is_healthy
        except Exception:
            status["score"] = "unknown"
            status["healthy"] = False
        return status
