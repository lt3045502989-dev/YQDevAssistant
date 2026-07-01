"""
Update Module — check for development tool updates.

Checks:
    - npm registry: npm, pnpm, Claude Code (automatic version comparison)
    - Report-only: Git, Python, Go, Node.js, VS Code, pip (current version)

Usage:
    yqa check update     # Check all tools for updates
    yqa run update       # Same as check (read-only, safe)
"""

from src.core.module_base import BaseModule, ModuleResult, ModuleInfo
from src.modules.update.version_checker import run_all_checks, UpdateItem


class UpdateModule(BaseModule):
    """
    Development tool update checker.

    check() — checks all tools for available updates
    execute() — same as check (update checks are read-only)
    """

    info = ModuleInfo(
        name="update",
        version="0.1.0",
        description="开发工具更新检查 — 检查 npm/pip/Git/Python/Go 等工具的更新",
        category="maintenance",
        icon="📦",
    )

    def check(self) -> ModuleResult:
        """
        Check all development tools for available updates.

        Returns:
            ModuleResult with data containing:
                - items: list of UpdateItem results
                - updates_available: count of tools with updates
                - checked: total tools checked
        """
        try:
            items = run_all_checks()

            updates_available = sum(1 for item in items if item.update_available)
            npm_checked = sum(1 for item in items if item.check_method == "npm")
            report_only = sum(1 for item in items if item.check_method == "report-only")

            data = {
                "items": [
                    {
                        "name": item.name,
                        "current": item.current_version,
                        "latest": item.latest_version or "?",
                        "update_available": item.update_available,
                        "update_command": item.update_command,
                        "method": item.check_method,
                    }
                    for item in items
                ],
                "updates_available": updates_available,
                "total_checked": len(items),
                "npm_checked": npm_checked,
                "report_only": report_only,
            }

            warnings = []
            if updates_available > 0:
                warnings.append(
                    f"{updates_available} tool(s) have updates available. "
                    "Use 'yqa run update' to see update commands."
                )

            return ModuleResult.ok(self.info.name, data, warnings)

        except Exception as e:
            return ModuleResult.fail(self.info.name, [str(e)])

    def execute(self, **kwargs) -> ModuleResult:
        """Same as check (update checking is always read-only)."""
        return self.check()

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            items = run_all_checks()
            updates = sum(1 for item in items if item.update_available)
            status["updates_available"] = updates
        except Exception:
            status["updates_available"] = "error"
        return status
