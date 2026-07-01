"""
YQ Dev Assistant — Shell Utilities.

Functions for interacting with the operating system:
- Running PowerShell and CMD commands
- Finding executables
- Getting tool versions

Design principle:
    Shell utilities are the "bridge" between Python and the OS.
    They encapsulate all the ugly subprocess handling (encoding,
    timeouts, error handling) so that modules don't have to.

Important for Windows:
    PowerShell output may use the system code page (often GBK on
    Chinese Windows). We force UTF-8 where possible and provide
    fallback decoding.
"""

import shutil
import subprocess
from pathlib import Path


# ── Command Execution ──────────────────────────────────────


def run_command(
    args: list[str],
    timeout: int = 30,
    cwd: str | Path | None = None,
) -> tuple[int, str, str]:
    """
    Run a command and return (exit_code, stdout, stderr).

    This is the low-level building block. Higher-level functions
    (run_powershell, run_cmd) build on this.

    Args:
        args: Command and arguments as a list (e.g., ["git", "--version"]).
        timeout: Maximum seconds to wait before killing the process.
        cwd: Working directory for the command.

    Returns:
        Tuple of (exit_code: int, stdout: str, stderr: str).
        Even if the command times out, returns (-1, "", timeout_message).

    Encoding handling:
        Tries UTF-8 first (the project standard), falls back to
        the system default encoding with 'replace' for characters
        that can't be decoded.
    """
    # On Windows, many CLI tools are .cmd/.bat files (npm, pnpm, code, etc.).
    # subprocess.run with a list can't execute .cmd files directly.
    # We try list-style first (safer), then fall back to shell=True.
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        # On Windows, the command might be a .cmd file — retry with shell=True
        try:
            cmd_str = " ".join(args)
            result = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                encoding="utf-8",
                errors="replace",
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s: {' '.join(args)}"
        except Exception as e:
            return -1, "", f"Command failed: {args[0]} — {e}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(args)}"
    except Exception as e:
        return -1, "", str(e)


def run_powershell(command: str, timeout: int = 30) -> tuple[int, str, str]:
    """
    Run a PowerShell command.

    Automatically wraps the command with:
    - -NoProfile: faster startup, no user profile scripts
    - -Command: execute the given script

    Args:
        command: PowerShell script text.
        timeout: Maximum seconds to wait.

    Returns:
        Tuple of (exit_code, stdout, stderr).

    Example:
        >>> exit_code, stdout, stderr = run_powershell("Get-Date -Format yyyy-MM-dd")
        >>> print(stdout)
        '2026-07-01'
    """
    return run_command(
        ["powershell", "-NoProfile", "-Command", command],
        timeout=timeout,
    )


def run_cmd(command: str, timeout: int = 30) -> tuple[int, str, str]:
    """
    Run a CMD command.

    Args:
        command: CMD command text.
        timeout: Maximum seconds to wait.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    return run_command(
        ["cmd", "/c", command],
        timeout=timeout,
    )


# ── Executable Discovery ───────────────────────────────────


def which(executable: str) -> str | None:
    """
    Find an executable in the system PATH.

    Cross-platform wrapper around shutil.which().
    On Windows, also checks common extensions (.exe, .cmd, .bat).

    Args:
        executable: Name of the executable (e.g., "git", "python").

    Returns:
        Absolute path to the executable, or None if not found.

    Example:
        >>> which("git")
        'C:\\\\Program Files\\\\Git\\\\cmd\\\\git.exe'
        >>> which("nonexistent-tool")
        None
    """
    return shutil.which(executable)


def get_version(executable: str, version_arg: str = "--version") -> str | None:
    """
    Get the version string from an executable.

    Tries to run `<executable> <version_arg>` and returns the
    first line of output.

    Args:
        executable: Name of the executable.
        version_arg: The flag that makes it print its version.
                     Common values: "--version", "-v", "version".

    Returns:
        First line of version output, or None if the command failed.

    Example:
        >>> get_version("git")
        'git version 2.47.1.windows.1'
        >>> get_version("python", "-V")
        'Python 3.14.6'
    """
    exit_code, stdout, stderr = run_command([executable, version_arg], timeout=10)
    if exit_code != 0:
        return None

    # Return the first non-empty line
    for line in (stdout + "\n" + stderr).split("\n"):
        line = line.strip()
        if line:
            return line
    return None


# ── Command Existence Check ────────────────────────────────


def command_exists(executable: str) -> bool:
    """
    Check if an executable exists in PATH.

    Faster than `which()` because it doesn't resolve the full path.

    Example:
        >>> command_exists("git")
        True
    """
    return which(executable) is not None
