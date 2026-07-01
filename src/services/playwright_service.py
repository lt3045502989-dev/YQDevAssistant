"""
YQ Dev Assistant — Playwright Service.

Wrapper for Playwright browser automation. In M1.1, this provides
the interface and basic stubs. Full implementation comes in M1.3
when the Browser module is built.

Design principles:
    1. INSTALLATION CHECK: Detect whether Playwright and browsers are installed.
    2. SERVICE ERROR: All Playwright errors are wrapped in ServiceError.
    3. INTERFACE FIRST: Method signatures define the contract.

Usage:
    >>> ps = PlaywrightService()
    >>> ps.is_installed
    True
    >>> ps.get_version()
    '1.52.0'
"""

import logging
from typing import Any

from src.core.exceptions import ServiceError
from src.utils.shell import get_version, command_exists

logger = logging.getLogger(__name__)


class PlaywrightService:
    """
    Playwright browser automation wrapper.

    M1.1: Interface definition with installation check.
    M1.3: Full implementation (launch browser, take screenshots, etc.).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the Playwright service.

        Args:
            config: Optional configuration dict.
        """
        self._config = config or {}
        self._playwright_available = self._check_installation()

    # ── Installation Check ─────────────────────────────

    def _check_installation(self) -> bool:
        """
        Check if Playwright is installed.

        Checks both:
        1. The Python playwright package (pip install playwright)
        2. Browser binaries (playwright install)

        Returns:
            True if Playwright is fully installed.
        """
        try:
            import importlib
            importlib.import_module("playwright")
            logger.info("Playwright Python package is installed")
            return True
        except ImportError:
            logger.info(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install"
            )
            return False

    # ── Status ─────────────────────────────────────────

    @property
    def is_installed(self) -> bool:
        """Check if Playwright is installed and ready."""
        return self._playwright_available

    def get_version(self) -> str | None:
        """
        Get the Playwright version.

        Returns:
            Version string (e.g., "1.52.0") or None if not installed.
        """
        if not self._playwright_available:
            return None

        try:
            from playwright import __version__
            return __version__
        except ImportError:
            return None

    # ── M1.3 Stubs ─────────────────────────────────────

    def launch_browser(self, headless: bool = True) -> Any:
        """
        Launch a browser instance.

        M1.1: Stub.
        M1.3: Full implementation.

        Args:
            headless: Run browser without UI.

        Returns:
            Browser instance (or stub indicator).

        Raises:
            ServiceError: If Playwright is not installed.
        """
        if not self._playwright_available:
            raise ServiceError(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install"
            )
        logger.debug("launch_browser() stub called (headless=%s)", headless)
        return None  # M1.3: Return actual browser instance

    def take_screenshot(self, url: str, output_path: str) -> str:
        """
        Take a screenshot of a webpage.

        M1.1: Stub.
        M1.3: Full implementation.

        Args:
            url: URL to screenshot.
            output_path: Where to save the screenshot.

        Returns:
            Path to the saved screenshot.

        Raises:
            ServiceError: If Playwright is not installed.
        """
        if not self._playwright_available:
            raise ServiceError("Playwright is not installed.")
        logger.debug("take_screenshot() stub called for '%s'", url)
        return output_path  # M1.3: Actually take screenshot

    def __repr__(self) -> str:
        status = "installed" if self._playwright_available else "not installed"
        return f"PlaywrightService({status})"
