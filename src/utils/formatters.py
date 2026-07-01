"""
YQ Dev Assistant — Output Formatters.

Pure functions that format data into human-readable strings.
Used by CLI output, log messages, and (future) GUI display.

Design principle:
    Formatters are PURE: given the same input, they always
    produce the same output. No side effects, no state.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.module_base import ModuleResult


# ── Duration ───────────────────────────────────────────────


def format_duration(ms: float) -> str:
    """
    Format milliseconds into a human-readable duration.

    Examples:
        >>> format_duration(1500)
        '1.50s'
        >>> format_duration(45)
        '45ms'
        >>> format_duration(120000)
        '2m 0s'
    """
    if ms < 1:
        return f"{int(ms * 1000)}μs"
    elif ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60_000:
        return f"{ms / 1000:.2f}s"
    else:
        minutes = int(ms / 60_000)
        seconds = int((ms % 60_000) / 1000)
        return f"{minutes}m {seconds}s"


# ── Bytes ──────────────────────────────────────────────────


def format_bytes(size_bytes: int) -> str:
    """
    Format bytes into a human-readable size.

    Examples:
        >>> format_bytes(1536)
        '1.50 KB'
        >>> format_bytes(1048576)
        '1.00 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.2f} MB"
    else:
        return f"{size_bytes / 1024**3:.2f} GB"


# ── Timestamp ──────────────────────────────────────────────


def format_timestamp(dt: datetime | None = None, local: bool = True) -> str:
    """
    Format a datetime for display.

    Args:
        dt: Datetime to format. Default: now.
        local: If True, convert to local time. If False, show UTC.

    Examples:
        >>> format_timestamp()
        '2026-07-01 14:30:00'
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if local and dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ── Text ───────────────────────────────────────────────────


def truncate(text: str, max_len: int = 80, ellipsis: str = "...") -> str:
    """
    Truncate a string to max_len, adding ellipsis if truncated.

    Examples:
        >>> truncate("Hello World", 8)
        'Hello...'
        >>> truncate("Hello", 8)
        'Hello'
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - len(ellipsis)] + ellipsis


# ── Module Result ──────────────────────────────────────────


def format_module_result(result: "ModuleResult", verbose: bool = False) -> str:
    """
    Format a ModuleResult for CLI display.

    Args:
        result: The ModuleResult to format.
        verbose: If True, include timestamps and durations.

    Returns:
        A multi-line string suitable for terminal output.
    """
    from src.core.module_base import ModuleResult

    lines = []

    # Status line
    if result.is_ok:
        status_icon = "✅"
        status_text = "PASS"
    elif result.success and result.has_errors:
        status_icon = "⚠️"
        status_text = "PARTIAL"
    else:
        status_icon = "❌"
        status_text = "FAIL"

    header = f"{status_icon} {result.module_name} — {status_text}"
    if verbose:
        header += f" ({format_duration(result.duration_ms)})"
    lines.append(header)

    # Warnings
    for w in result.warnings:
        lines.append(f"  ⚠ {w}")

    # Errors
    for e in result.errors:
        lines.append(f"  ✗ {e}")

    # Timestamp (verbose only)
    if verbose and result.timestamp:
        lines.append(f"  ── {format_timestamp(result.timestamp)}")

    return "\n".join(lines)


# ── Simple Table ───────────────────────────────────────────


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Format data as a simple aligned table.

    Falls back to Rich's Table if available, otherwise
    uses plain-text column alignment.

    Example:
        >>> format_table(["Name", "Version"], [["health", "0.1.0"], ["backup", "0.1.0"]])
        Name     Version
        health   0.1.0
        backup   0.1.0
    """
    try:
        from rich.table import Table
        from rich.console import Console

        table = Table()
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*row)

        # Capture to string
        console = Console(width=120)
        with console.capture() as capture:
            console.print(table)
        return capture.get().rstrip()
    except ImportError:
        # Fallback: plain text alignment
        if not rows:
            return "  ".join(headers) + "\n(empty)"

        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        lines = []
        # Header
        header_line = "  ".join(
            h.ljust(col_widths[i]) for i, h in enumerate(headers)
        )
        lines.append(header_line)
        lines.append("-" * len(header_line))
        # Rows
        for row in rows:
            padded = []
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    padded.append(str(cell).ljust(col_widths[i]))
                else:
                    padded.append(str(cell))
            lines.append("  ".join(padded))

        return "\n".join(lines)
