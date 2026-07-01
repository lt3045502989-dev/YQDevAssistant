"""
Version Checker — check for updates to development tools.

Two types of checks:
    1. npm registry: npm, pnpm, Claude Code (via `npm view <pkg> version`)
    2. Report-only: Git, Python, Go, Node.js, VS Code (can't auto-check latest)

Design:
    - Each check returns an UpdateItem
    - update_available is True when a newer version is found
    - update_command provides the recommended update command
"""

from dataclasses import dataclass
from src.utils.shell import get_version, run_command


@dataclass
class UpdateItem:
    """Result of checking a single tool for updates."""

    name: str
    current_version: str
    latest_version: str | None = None  # None = can't auto-check
    update_available: bool = False
    update_command: str = ""
    check_method: str = "report-only"  # "npm" or "report-only"


# ── npm Registry Checks ────────────────────────────────────

# Tools that can be checked via npm: (display_name, package_name, update_command)
NPM_PACKAGES = [
    ("npm", "npm", "npm install -g npm@latest"),
    ("pnpm", "pnpm", "npm install -g pnpm@latest"),
    ("Claude Code", "@anthropic-ai/claude-code", "npm update -g @anthropic-ai/claude-code"),
]


def check_npm_package(name: str, package: str, update_cmd: str) -> UpdateItem:
    """
    Check a tool's version against the latest on the npm registry.

    Args:
        name: Display name.
        package: npm package name.
        update_cmd: Command to update if a newer version exists.

    Returns:
        UpdateItem with comparison result.
    """
    current = _get_npm_current(package)
    latest = _get_npm_latest(package)

    if current is None:
        return UpdateItem(
            name=name,
            current_version="unknown",
            latest_version=latest,
            check_method="npm",
        )

    if latest is None:
        return UpdateItem(
            name=name,
            current_version=current,
            latest_version=None,
            update_available=False,
            check_method="npm",
        )

    update_available = current != latest

    return UpdateItem(
        name=name,
        current_version=current,
        latest_version=latest,
        update_available=update_available,
        update_command=update_cmd if update_available else "",
        check_method="npm",
    )


def _get_npm_current(package: str) -> str | None:
    """Get the installed version of an npm package."""
    if package == "npm":
        return get_version("npm", "-v")
    elif package == "pnpm":
        return get_version("pnpm", "-v")
    else:
        # For Claude Code and other packages, try <command> --version
        cmd = package.split("/")[-1]  # @anthropic-ai/claude-code → claude-code
        if cmd.startswith("claude"):
            cmd = "claude"
        version = get_version(cmd, "--version")
        if version:
            # Extract just the version number from "2.1.197 (Claude Code)"
            import re
            match = re.search(r"(\d+\.\d+\.\d+)", version)
            if match:
                return match.group(1)
            return version.split()[0] if version.split() else version
        return None


def _get_npm_latest(package: str) -> str | None:
    """Get the latest version of an npm package from the registry."""
    exit_code, stdout, stderr = run_command(
        ["npm", "view", package, "version"],
        timeout=15,
    )
    if exit_code == 0 and stdout:
        return stdout.strip().split("\n")[-1]  # Last line is the version
    return None


def check_all_npm_packages() -> list[UpdateItem]:
    """Check all npm-based tools for updates."""
    return [check_npm_package(name, pkg, cmd) for name, pkg, cmd in NPM_PACKAGES]


# ── Report-Only Checks ─────────────────────────────────────

# Tools where we can only report current version: (name, command, version_arg)
REPORT_ONLY_TOOLS = [
    ("Git", "git", "--version"),
    ("Python", "python", "--version"),
    ("Go", "go", "version"),
    ("Node.js", "node", "-v"),
    ("VS Code", "code", "--version"),
]


def check_report_only(name: str, command: str, version_arg: str) -> UpdateItem:
    """
    Report the current version of a tool (can't auto-check for updates).

    Args:
        name: Display name.
        command: Executable.
        version_arg: Version flag.

    Returns:
        UpdateItem with current version only.
    """
    version = get_version(command, version_arg)
    if version:
        # Extract first line and truncate
        version = version.split("\n")[0]
        if len(version) > 60:
            version = version[:57] + "..."
    else:
        version = "not found"

    return UpdateItem(
        name=name,
        current_version=version,
        latest_version=None,
        update_available=False,
        check_method="report-only",
    )


def check_all_report_only() -> list[UpdateItem]:
    """Check all report-only tools."""
    return [check_report_only(name, cmd, arg) for name, cmd, arg in REPORT_ONLY_TOOLS]


# ── pip (special case) ─────────────────────────────────────


def check_pip() -> UpdateItem:
    """
    Check pip version (report-only for now).

    pip can self-update with `pip install --upgrade pip`,
    but checking the latest version on PyPI requires parsing JSON API.
    """
    version = get_version("pip", "--version")
    if version:
        version = version.split()[1] if len(version.split()) > 1 else version
    else:
        version = "not found"

    return UpdateItem(
        name="pip",
        current_version=version,
        latest_version=None,
        update_available=False,
        update_command="pip install --upgrade pip",
        check_method="report-only",
    )


# ── Run All ────────────────────────────────────────────────


def run_all_checks() -> list[UpdateItem]:
    """Run all update checks."""
    results = []

    # npm-based
    results.extend(check_all_npm_packages())

    # pip
    results.append(check_pip())

    # Report-only
    results.extend(check_all_report_only())

    return results
