"""
YQ Dev Assistant — Input Validators.

Pure functions that validate data. They:
- Take input, return bool
- Have NO side effects
- Have NO state
- Are trivially testable

Design principle:
    Validators answer a single yes/no question.
    They do NOT raise exceptions (that's the caller's job).
    This makes them composable and easy to test.
"""

import re
from urllib.parse import urlparse


# ── Module Names ───────────────────────────────────────────

_MODULE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


def validate_module_name(name: str) -> bool:
    """
    Check if a string is a valid module name.

    Rules:
    - Lowercase letters, digits, and underscores only
    - Must start with a letter
    - 2 to 50 characters

    Examples:
        >>> validate_module_name("health")
        True
        >>> validate_module_name("Health")
        False
        >>> validate_module_name("x")
        False
    """
    return bool(_MODULE_NAME_RE.match(name))


# ── URLs ───────────────────────────────────────────────────


def validate_url(url: str) -> bool:
    """
    Check if a string looks like a valid URL.

    Examples:
        >>> validate_url("https://github.com")
        True
        >>> validate_url("not-a-url")
        False
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except (ValueError, AttributeError):
        return False


# ── Versions ───────────────────────────────────────────────

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$")


def validate_semver(version: str) -> bool:
    """
    Check if a string is valid semantic versioning.

    Examples:
        >>> validate_semver("1.2.3")
        True
        >>> validate_semver("1.2.3-alpha.1")
        True
        >>> validate_semver("v1.2.3")
        False
    """
    return bool(_SEMVER_RE.match(version))


# ── Paths ──────────────────────────────────────────────────


def validate_path_safe(path: str, allowed_root: str = "C:/Users/L1372") -> bool:
    """
    Check if a path is within the allowed root directory.

    This is a SECURITY check — it prevents modules from accidentally
    or maliciously operating on files outside the allowed area.

    Uses string prefix matching (case-insensitive on Windows).

    Examples:
        >>> validate_path_safe("C:/Users/L1372/Documents/file.txt")
        True
        >>> validate_path_safe("C:/Windows/System32/file.dll")
        False
    """
    import os
    from pathlib import Path

    try:
        resolved = Path(path).resolve()
        root = Path(allowed_root).resolve()
        # On Windows, paths are case-insensitive
        resolved_str = str(resolved).lower()
        root_str = str(root).lower()
        return resolved_str.startswith(root_str)
    except (ValueError, OSError):
        return False
