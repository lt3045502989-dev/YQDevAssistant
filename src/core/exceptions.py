"""
YQ Dev Assistant — Exception Hierarchy.

Design principle:
    Every exception type answers two questions:
    1. WHAT went wrong?  (the exception class)
    2. WHAT should happen next?  (the exit_code)

Catching granularity:
    - catch YQAError     → handle ANY app error
    - catch ConfigError  → handle ONLY config problems
    - catch ModuleError  → handle ONLY module issues

This is like circuit breakers in a house:
    YQAError    = main breaker (shuts off everything)
    ConfigError = room breaker (shuts off one room)
"""

from typing import Any


class YQAError(Exception):
    """
    Base exception for ALL errors originating from YQ Dev Assistant.

    Every custom exception in this project inherits from this class.
    This means you can write:
        try:
            ...
        except YQAError:
            # catches any YQA-specific error, but lets system errors through
            ...

    Attributes:
        message: Human-readable error description.
        exit_code: Suggested process exit code for CLI usage.
        details: Optional extra data for debugging (not shown to users by default).
    """

    exit_code: int = 1  # Default: general error

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return self.message


# ── Configuration Errors ──────────────────────────────────


class ConfigError(YQAError):
    """
    Configuration-related errors.

    Raised when:
    - Config file is missing or unreadable
    - Config does not match the JSON Schema
    - A required config key is missing
    - A config value is the wrong type
    """

    exit_code = 2


# ── Module Errors ─────────────────────────────────────────


class ModuleError(YQAError):
    """
    Module lifecycle errors.

    Raised when:
    - A module is not found (unknown module name)
    - A module fails to load (import error, syntax error)
    - A module's check() or execute() crashes
    """

    exit_code = 3


class ModuleNotFoundError(ModuleError):
    """
    Specific: the requested module does not exist.

    Separate from ModuleError so callers can distinguish
    'module not there' from 'module is there but broken'.
    """

    exit_code = 3


# ── Service Errors ────────────────────────────────────────


class ServiceError(YQAError):
    """
    External service errors.

    Raised when:
    - GitHub API is unreachable or returns an error
    - Network request times out
    - Playwright is not installed
    - File operation fails (permission denied, disk full)
    """

    exit_code = 4


# ── Validation Errors ─────────────────────────────────────


class ValidationError(YQAError):
    """
    Input or data validation errors.

    Raised when:
    - User input fails validation (bad module name, invalid URL)
    - A path is outside the allowed root
    - A value is the wrong type or format
    """

    exit_code = 5
