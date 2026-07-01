"""
YQ Dev Assistant — GitHub Service.

Wrapper for GitHub API operations. In M1.1, this provides the interface
and basic stubs. Full implementation comes in M1.3 when the GitHub module
is built (using PyGithub or direct API calls).

Design principles:
    1. AUTHENTICATION: Token is read from environment variables or config.
    2. SERVICE ERROR: All API errors are wrapped in ServiceError.
    3. INTERFACE FIRST: Even as stubs, the method signatures define
       the contract for future implementation.

Usage:
    >>> gs = GitHubService(config={"user": "lt3045502989-dev"})
    >>> gs.is_authenticated
    False  # No token configured yet
"""

import logging
import os
from typing import Any

from src.core.exceptions import ServiceError

logger = logging.getLogger(__name__)


class GitHubService:
    """
    GitHub API wrapper.

    M1.1: Interface definition with basic stubs.
    M1.3: Full implementation (list repos, create issues, etc.).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the GitHub service.

        Args:
            config: Dict with keys: api_base, token_env_var, user.
        """
        self._config = config or {}
        self._api_base = self._config.get("api_base", "https://api.github.com")
        self._token_env_var = self._config.get("token_env_var", "GITHUB_TOKEN")
        self._username = self._config.get("user", "")

        # Try to load token from environment
        self._token = os.environ.get(self._token_env_var)
        if self._token:
            logger.info(
                "GitHubService authenticated as '%s' (token from %s)",
                self._username,
                self._token_env_var,
            )
        else:
            logger.info(
                "GitHubService initialized without token "
                "(set %s environment variable for full access)",
                self._token_env_var,
            )

    # ── Status ─────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """Check if a GitHub token is configured."""
        return bool(self._token)

    @property
    def username(self) -> str:
        """The configured GitHub username."""
        return self._username

    # ── API Stubs (M1.3 implementation) ────────────────

    def get_user(self, username: str) -> dict[str, Any]:
        """
        Get GitHub user information.

        M1.1: Stub — returns basic info from config.
        M1.3: Full API call.

        Args:
            username: GitHub username.

        Returns:
            User information dict.

        Raises:
            ServiceError: If not authenticated.
        """
        if not self.is_authenticated:
            raise ServiceError(
                "GitHub API requires authentication. "
                f"Set the {self._token_env_var} environment variable."
            )
        # TODO M1.3: Actual API call
        logger.debug("get_user() stub called for '%s'", username)
        return {"login": username, "html_url": f"https://github.com/{username}"}

    def list_repos(self, username: str | None = None) -> list[dict[str, Any]]:
        """
        List repositories for a user.

        M1.1: Stub — returns empty list.
        M1.3: Full API call.

        Args:
            username: GitHub username. Defaults to authenticated user.

        Returns:
            List of repository info dicts.

        Raises:
            ServiceError: If not authenticated.
        """
        if not self.is_authenticated:
            raise ServiceError(
                "GitHub API requires authentication."
            )
        # TODO M1.3: Actual API call
        logger.debug("list_repos() stub called for '%s'", username or self._username)
        return []

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """
        Get information about a specific repository.

        M1.1: Stub.
        M1.3: Full API call.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Repository info dict.

        Raises:
            ServiceError: If not authenticated or repo not found.
        """
        if not self.is_authenticated:
            raise ServiceError("GitHub API requires authentication.")
        # TODO M1.3: Actual API call
        logger.debug("get_repo() stub called for '%s/%s'", owner, repo)
        return {
            "full_name": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
        }

    def __repr__(self) -> str:
        auth = "authenticated" if self.is_authenticated else "not authenticated"
        return f"GitHubService(user={self._username}, {auth})"
