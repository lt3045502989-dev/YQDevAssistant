"""
YQ Dev Assistant — Network Service.

HTTP client with proxy support. All network requests should go through
this service so that proxy configuration is handled in one place.

Design principles:
    1. SINGLE SOURCE OF TRUTH for proxy settings (from ConfigManager).
    2. TIMEOUT BY DEFAULT: Every request has a timeout. No hanging forever.
    3. SERVICE ERROR on failure: Network errors are wrapped in ServiceError
       with clear messages (not raw ConnectionError).

Usage:
    >>> ns = NetworkService(proxy_config={"enabled": True, "http": "http://127.0.0.1:7897"})
    >>> response = ns.get("https://api.github.com")
    >>> ns.check_connectivity()  # Quick health check
    True
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.exceptions import ServiceError
from src.utils.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_PROXY_HTTP,
    DEFAULT_PROXY_HTTPS,
)

logger = logging.getLogger(__name__)


class NetworkService:
    """
    HTTP client with proxy support and sensible defaults.

    Wraps the `requests` library with:
    - Automatic proxy configuration
    - Default timeouts (never hang forever)
    - Retry logic for transient failures
    - ServiceError wrapping for clean error handling
    """

    def __init__(
        self,
        proxy_config: dict[str, Any] | None = None,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        """
        Initialize the network service.

        Args:
            proxy_config: Dict with keys: enabled, http, https.
                          If None, no proxy is used.
            timeout: Default timeout in seconds for all requests.
            max_retries: Number of retries for transient failures.
        """
        self._proxy_config = proxy_config or {"enabled": False}
        self._timeout = timeout

        # Create a requests Session for connection reuse
        self._session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        # Configure proxy
        if self._proxy_config.get("enabled", False):
            self._proxies = {
                "http": self._proxy_config.get("http", DEFAULT_PROXY_HTTP),
                "https": self._proxy_config.get("https", DEFAULT_PROXY_HTTPS),
            }
            logger.info(
                "NetworkService initialized with proxy: %s", self._proxies["http"]
            )
        else:
            self._proxies = None
            logger.info("NetworkService initialized without proxy")

    # ── HTTP Methods ───────────────────────────────────

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """
        Send a GET request.

        Args:
            url: Target URL.
            **kwargs: Additional arguments passed to requests.get().

        Returns:
            Response object.

        Raises:
            ServiceError: On connection failure, timeout, or HTTP error.
        """
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """
        Send a POST request.

        Args:
            url: Target URL.
            **kwargs: Additional arguments passed to requests.post().

        Returns:
            Response object.

        Raises:
            ServiceError: On connection failure, timeout, or HTTP error.
        """
        return self._request("POST", url, **kwargs)

    # ── Connectivity ───────────────────────────────────

    def check_connectivity(
        self, url: str = "https://github.com", timeout: int = 5
    ) -> bool:
        """
        Quick check if a URL is reachable.

        Used by Health module to verify network connectivity.
        Uses a HEAD request (faster than GET, no body).

        Args:
            url: URL to check. Default: GitHub (most important for dev work).
            timeout: Max seconds to wait.

        Returns:
            True if the URL responds (any 2xx/3xx status), False otherwise.
        """
        try:
            response = self._session.head(
                url,
                timeout=timeout,
                proxies=self._proxies,
                allow_redirects=True,
            )
            return response.ok
        except requests.RequestException as e:
            logger.debug("Connectivity check failed for %s: %s", url, e)
            return False

    def download_file(self, url: str, dest: str) -> Path:
        """
        Download a file to the specified destination.

        Args:
            url: File URL.
            dest: Destination path (string or Path).

        Returns:
            Path to the downloaded file.

        Raises:
            ServiceError: On download failure.
        """
        from pathlib import Path

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            response = self._session.get(
                url,
                timeout=self._timeout * 2,  # Downloads may take longer
                proxies=self._proxies,
                stream=True,
            )
            response.raise_for_status()

            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(
                "Downloaded %s → %s (%d bytes)",
                url,
                dest_path,
                dest_path.stat().st_size,
            )
            return dest_path

        except requests.RequestException as e:
            raise ServiceError(
                f"Failed to download {url}: {e}",
                details={"url": url, "dest": str(dest_path)},
            ) from e

    # ── Internal ───────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Execute an HTTP request with error handling."""
        # Apply defaults (caller can override)
        kwargs.setdefault("timeout", self._timeout)
        kwargs.setdefault("proxies", self._proxies)

        try:
            response = self._session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.Timeout as e:
            raise ServiceError(
                f"Request to {url} timed out after {kwargs['timeout']}s. "
                f"Is the proxy running?",
                details={"url": url, "timeout": kwargs["timeout"]},
            ) from e
        except requests.ConnectionError as e:
            raise ServiceError(
                f"Cannot connect to {url}. Check your network and proxy settings.",
                details={"url": url, "proxy": str(self._proxies)},
            ) from e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            raise ServiceError(
                f"HTTP {status} from {url}",
                details={"url": url, "status": status},
            ) from e
        except requests.RequestException as e:
            raise ServiceError(
                f"Request failed: {e}",
                details={"url": url, "method": method},
            ) from e

    @property
    def is_proxy_enabled(self) -> bool:
        """Check if proxy is currently enabled."""
        return self._proxies is not None

    def __repr__(self) -> str:
        proxy = self._proxies["http"] if self._proxies else "none"
        return f"NetworkService(proxy={proxy}, timeout={self._timeout}s)"
