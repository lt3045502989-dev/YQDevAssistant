"""
Health Checker — individual health checks for the development environment.

Each check is a function that:
    - Takes no arguments (or minimal config)
    - Returns a CheckItem (status, message, score_deduction)
    - Never raises exceptions (errors are captured as CheckItems)

Design: each check is INDEPENDENT. You can add, remove, or reorder
checks without affecting anything else.

The scoring model (from weekly-health.sh):
    - Start at 100
    - Deduct points for each issue found
    - Final score: < 60 = critical, 60-74 = needs attention,
                   75-89 = good, 90+ = excellent
"""

from dataclasses import dataclass, field
from src.utils.shell import command_exists, get_version, run_powershell


# ── Data Model ─────────────────────────────────────────────


@dataclass
class CheckItem:
    """
    Result of a single health check.

    Attributes:
        name: Check name (e.g., "Git", "Disk Space").
        status: "pass" | "warn" | "fail"
        message: Human-readable description of the result.
        score_deduction: Points to deduct from the health score (0 = no issue).
        detail: Optional extra info (version number, size, etc.).
    """

    name: str
    status: str  # "pass", "warn", "fail"
    message: str
    score_deduction: int = 0
    detail: str = ""

    @property
    def is_ok(self) -> bool:
        return self.status == "pass"

    @property
    def is_warning(self) -> bool:
        return self.status == "warn"

    @property
    def is_failure(self) -> bool:
        return self.status == "fail"


# ── Tool Checks ────────────────────────────────────────────

# Each tool is defined by: (name, command, version_arg, score_deduction_if_missing)
TOOLS = [
    ("Git", "git", "--version", 10),
    ("Node.js", "node", "-v", 10),
    ("npm", "npm", "-v", 5),
    ("pnpm", "pnpm", "-v", 5),
    ("Python", "python", "--version", 10),
    ("pip", "pip", "--version", 5),
    ("Go", "go", "version", 5),
    ("VS Code", "code", "--version", 5),
    ("Claude Code", "claude", "--version", 5),
    ("Codex CLI", "codex", "--version", 5),
]


def check_tool(name: str, command: str, version_arg: str, deduction: int) -> CheckItem:
    """
    Check if a development tool is installed and get its version.

    Args:
        name: Display name of the tool.
        command: Executable name (e.g., "git").
        version_arg: Flag to get version (e.g., "--version").
        deduction: Points to deduct if the tool is missing.

    Returns:
        CheckItem with status and version detail.
    """
    if not command_exists(command):
        return CheckItem(
            name=name,
            status="fail",
            message=f"{name} 未安装或不在 PATH 中",
            score_deduction=deduction,
        )

    version = get_version(command, version_arg)
    if version:
        # Truncate very long version strings
        if len(version) > 80:
            version = version[:77] + "..."
        return CheckItem(
            name=name,
            status="pass",
            message=f"{name} 已安装",
            detail=version,
        )
    else:
        return CheckItem(
            name=name,
            status="warn",
            message=f"{name} 已安装但无法获取版本",
            score_deduction=2,
            detail="版本未知",
        )


def check_all_tools() -> list[CheckItem]:
    """Run all tool checks."""
    return [check_tool(name, cmd, arg, ded) for name, cmd, arg, ded in TOOLS]


# ── Network Checks ─────────────────────────────────────────


def check_network_github(timeout: int = 5) -> CheckItem:
    """
    Check if GitHub is reachable.

    Uses a HEAD request for speed (no body downloaded).
    """
    try:
        import requests
        r = requests.head("https://github.com", timeout=timeout, allow_redirects=True)
        if r.ok:
            return CheckItem(
                name="GitHub 连接",
                status="pass",
                message="GitHub 可连接",
                detail=f"响应时间: {r.elapsed.total_seconds():.2f}s",
            )
        else:
            return CheckItem(
                name="GitHub 连接",
                status="warn",
                message=f"GitHub 返回 HTTP {r.status_code}",
                score_deduction=5,
                detail=f"状态码: {r.status_code}",
            )
    except Exception as e:
        return CheckItem(
            name="GitHub 连接",
            status="warn",
            message="GitHub 无法连接（检查代理是否开启）",
            score_deduction=5,
            detail=str(e),
        )


def check_network_google(timeout: int = 5) -> CheckItem:
    """Check if Google is reachable."""
    try:
        import requests
        r = requests.head("https://www.google.com", timeout=timeout, allow_redirects=True)
        if r.ok:
            return CheckItem(
                name="Google 连接",
                status="pass",
                message="Google 可连接",
                detail=f"响应时间: {r.elapsed.total_seconds():.2f}s",
            )
        else:
            return CheckItem(
                name="Google 连接",
                status="warn",
                message=f"Google 返回 HTTP {r.status_code}",
                score_deduction=2,
            )
    except Exception:
        return CheckItem(
            name="Google 连接",
            status="warn",
            message="Google 无法连接（可能需要代理）",
            score_deduction=2,
        )


# ── System Checks ──────────────────────────────────────────


def check_disk_space(drive_letter: str = "C") -> CheckItem:
    """
    Check free disk space on the specified drive.

    Uses PowerShell on Windows to get volume information.
    """
    result = run_powershell(
        f"$v = Get-Volume -DriveLetter {drive_letter}; "
        f"$free = [math]::Round($v.SizeRemaining/1GB, 1); "
        f"$total = [math]::Round($v.Size/1GB, 1); "
        f"$pct = [math]::Round(($v.Size - $v.SizeRemaining)/$v.Size*100, 1); "
        f"Write-Host \"$free|$total|$pct\""
    )

    exit_code, stdout, stderr = result

    if exit_code != 0 or not stdout:
        return CheckItem(
            name="磁盘空间",
            status="warn",
            message="无法获取磁盘信息",
            score_deduction=5,
        )

    try:
        parts = stdout.strip().split("|")
        free_gb = float(parts[0])
        total_gb = float(parts[1])
        used_pct = float(parts[2])

        detail = f"{free_gb} GB 可用 / {total_gb} GB 总计 ({used_pct}% 已用)"

        if used_pct > 90:
            return CheckItem(
                name="磁盘空间",
                status="fail",
                message=f"磁盘空间严重不足（{used_pct}% 已用）",
                score_deduction=15,
                detail=detail,
            )
        elif used_pct > 80:
            return CheckItem(
                name="磁盘空间",
                status="warn",
                message=f"磁盘使用超过 80%，建议清理",
                score_deduction=10,
                detail=detail,
            )
        elif used_pct > 70:
            return CheckItem(
                name="磁盘空间",
                status="pass",
                message="磁盘空间正常",
                detail=detail,
            )
        else:
            return CheckItem(
                name="磁盘空间",
                status="pass",
                message="磁盘空间充足",
                detail=detail,
            )
    except (ValueError, IndexError):
        return CheckItem(
            name="磁盘空间",
            status="warn",
            message="无法解析磁盘信息",
            score_deduction=5,
            detail=stdout.strip(),
        )


def check_memory() -> CheckItem:
    """
    Check available physical memory.

    Uses PowerShell WMI to get memory stats.
    """
    result = run_powershell(
        "$os = Get-WmiObject Win32_OperatingSystem; "
        "$totalGB = [math]::Round($os.TotalVisibleMemorySize/1MB); "
        "$freeGB = [math]::Round($os.FreePhysicalMemory/1MB); "
        "$usedGB = $totalGB - $freeGB; "
        "$pct = [math]::Round(($totalGB - $freeGB)/$totalGB*100); "
        "Write-Host \"$usedGB|$totalGB|$pct\""
    )

    exit_code, stdout, stderr = result

    if exit_code != 0 or not stdout:
        return CheckItem(
            name="内存",
            status="warn",
            message="无法获取内存信息",
            score_deduction=5,
        )

    try:
        parts = stdout.strip().split("|")
        used_mb = float(parts[0])
        total_mb = float(parts[1])
        used_pct = float(parts[2])

        detail = f"{used_mb:.0f} GB / {total_mb:.0f} GB 已用 ({used_pct}%)"

        if used_pct > 90:
            return CheckItem(
                name="内存",
                status="warn",
                message=f"内存使用率很高（{used_pct}%）",
                score_deduction=5,
                detail=detail,
            )
        else:
            return CheckItem(
                name="内存",
                status="pass",
                message="内存正常",
                detail=detail,
            )
    except (ValueError, IndexError):
        return CheckItem(
            name="内存",
            status="warn",
            message="无法解析内存信息",
            score_deduction=5,
        )


def check_windows_defender() -> CheckItem:
    """
    Check if Windows Defender is running.

    Uses PowerShell to query Defender status.
    """
    result = run_powershell(
        "$s = Get-MpComputerStatus; "
        "if ($s.AntivirusEnabled -and $s.RealTimeProtectionEnabled) { "
        "Write-Host 'OK' } else { Write-Host 'ISSUE' }"
    )

    exit_code, stdout, stderr = result

    if exit_code == 0 and stdout.strip() == "OK":
        return CheckItem(
            name="安全防护",
            status="pass",
            message="Windows Defender 正常运行",
        )
    else:
        return CheckItem(
            name="安全防护",
            status="warn",
            message="Windows Defender 可能异常",
            score_deduction=15,
            detail=stdout.strip() if stdout else stderr,
        )


def check_temp_files(max_size_mb: int = 1000) -> CheckItem:
    """
    Check the size of the Windows Temp directory.

    Args:
        max_size_mb: Threshold in MB before warning.
    """
    from pathlib import Path
    temp_dir = Path.home() / "AppData" / "Local" / "Temp"

    if not temp_dir.exists():
        return CheckItem(
            name="临时文件",
            status="pass",
            message="无法检查临时文件目录",
        )

    # Calculate total size
    try:
        total_size = sum(
            f.stat().st_size for f in temp_dir.rglob("*") if f.is_file()
        )
        size_mb = total_size / (1024**2)

        if size_mb > max_size_mb:
            return CheckItem(
                name="临时文件",
                status="warn",
                message=f"临时文件目录: {size_mb:.0f} MB（超过 {max_size_mb} MB，建议清理）",
                score_deduction=5,
                detail=f"{size_mb:.0f} MB",
            )
        else:
            return CheckItem(
                name="临时文件",
                status="pass",
                message=f"临时文件目录: {size_mb:.0f} MB（正常）",
                detail=f"{size_mb:.0f} MB",
            )
    except Exception as e:
        return CheckItem(
            name="临时文件",
            status="warn",
            message=f"无法计算临时文件大小",
            detail=str(e),
        )


# ── Batch Check ────────────────────────────────────────────


def run_all_checks() -> list[CheckItem]:
    """
    Run ALL health checks and return the full list.

    This is the main entry point for the check logic.
    Returns a flat list of all CheckItems.
    """
    results = []

    # Tool checks
    results.extend(check_all_tools())

    # Network checks
    results.append(check_network_github())
    results.append(check_network_google())

    # System checks
    results.append(check_disk_space())
    results.append(check_memory())
    results.append(check_windows_defender())
    results.append(check_temp_files())

    return results
