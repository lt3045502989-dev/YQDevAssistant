"""
YQ Dev Assistant — File System Service.

Safe filesystem operations constrained to an allowed root directory.
This is a SECURITY boundary: even if a buggy module tries to operate
outside C:/Users/L1372, this service will refuse.

Design principles:
    1. SAFETY FIRST: Every path is validated to be within the allowed root.
    2. CONVENIENCE: Common operations (read/write JSON, list dirs) are
       wrapped in simple methods.
    3. SERVICE ERROR: All filesystem errors are wrapped in ServiceError
       with clear context (which path, what operation).

Usage:
    >>> fs = FileSystemService(allowed_root="C:/Users/L1372")
    >>> fs.ensure_dir("C:/Users/L1372/Projects")
    >>> content = fs.read_text("C:/Users/L1372/Projects/README.md")
"""

import json
import logging
import shutil
from pathlib import Path

from src.core.exceptions import ServiceError
from src.utils.constants import ALLOWED_FS_ROOT

logger = logging.getLogger(__name__)


class FileSystemService:
    """
    Safe filesystem operations within an allowed root directory.

    All paths are validated before any operation. Operations on paths
    outside the allowed root raise ServiceError.

    Uses pathlib.Path throughout for cross-platform compatibility.
    """

    def __init__(self, allowed_root: str | Path = ALLOWED_FS_ROOT) -> None:
        """
        Initialize the filesystem service.

        Args:
            allowed_root: The root directory for all operations.
                          All paths must be within this directory.
        """
        self._allowed_root = Path(allowed_root).resolve()
        logger.info(
            "FileSystemService initialized with allowed root: %s",
            self._allowed_root,
        )

    # ── Safety Check ───────────────────────────────────

    def is_safe_path(self, path: str | Path) -> bool:
        """
        Check if a path is within the allowed root.

        Resolves symlinks and relative paths before checking.
        Case-insensitive on Windows.

        Args:
            path: Path to check.

        Returns:
            True if the path is safe to operate on.
        """
        try:
            resolved = Path(path).resolve()
            # Case-insensitive comparison for Windows
            return (
                str(resolved).lower().startswith(str(self._allowed_root).lower())
            )
        except (ValueError, OSError):
            return False

    def _validate_path(self, path: str | Path) -> Path:
        """
        Validate and resolve a path.

        Returns the resolved Path if safe, raises ServiceError otherwise.
        """
        resolved = Path(path).resolve()
        if not self.is_safe_path(resolved):
            raise ServiceError(
                f"Path is outside the allowed root: {path}",
                details={
                    "path": str(path),
                    "resolved": str(resolved),
                    "allowed_root": str(self._allowed_root),
                },
            )
        return resolved

    # ── Directory Operations ───────────────────────────

    def ensure_dir(self, path: str | Path) -> Path:
        """
        Create a directory (and all parents) if it doesn't exist.

        Args:
            path: Directory path.

        Returns:
            Path to the created/existing directory.

        Raises:
            ServiceError: If path is unsafe or creation fails.
        """
        safe_path = self._validate_path(path)
        safe_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", safe_path)
        return safe_path

    def list_directory(
        self, path: str | Path, pattern: str = "*"
    ) -> list[Path]:
        """
        List files and directories matching a glob pattern.

        Args:
            path: Directory to list.
            pattern: Glob pattern (e.g., "*.py", "**/*.json").

        Returns:
            Sorted list of matching Path objects.

        Raises:
            ServiceError: If path is unsafe or not a directory.
        """
        safe_path = self._validate_path(path)
        if not safe_path.is_dir():
            raise ServiceError(
                f"Not a directory: {path}",
                details={"path": str(safe_path)},
            )

        entries = sorted(safe_path.glob(pattern))
        logger.debug("Listed %d entries in %s (pattern: %s)", len(entries), safe_path, pattern)
        return entries

    # ── File Read/Write ────────────────────────────────

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """
        Read a text file.

        Args:
            path: File path.
            encoding: Text encoding (default: UTF-8).

        Returns:
            File contents as a string.

        Raises:
            ServiceError: If path is unsafe, file not found, or read fails.
        """
        safe_path = self._validate_path(path)
        try:
            return safe_path.read_text(encoding=encoding)
        except FileNotFoundError:
            raise ServiceError(
                f"File not found: {path}",
                details={"path": str(safe_path)},
            )
        except Exception as e:
            raise ServiceError(
                f"Failed to read {path}: {e}",
                details={"path": str(safe_path)},
            ) from e

    def write_text(
        self, path: str | Path, content: str, encoding: str = "utf-8"
    ) -> None:
        """
        Write text to a file. Creates parent directories if needed.

        Args:
            path: File path.
            content: Text content to write.
            encoding: Text encoding (default: UTF-8).

        Raises:
            ServiceError: If path is unsafe or write fails.
        """
        safe_path = self._validate_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            safe_path.write_text(content, encoding=encoding)
            logger.debug("Wrote %d chars to %s", len(content), safe_path)
        except Exception as e:
            raise ServiceError(
                f"Failed to write {path}: {e}",
                details={"path": str(safe_path)},
            ) from e

    def read_json(self, path: str | Path) -> dict:
        """
        Read and parse a JSON file.

        Args:
            path: JSON file path.

        Returns:
            Parsed JSON as a dictionary.

        Raises:
            ServiceError: If path is unsafe, file not found, or JSON is invalid.
        """
        text = self.read_text(path)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ServiceError(
                f"Invalid JSON in {path}: {e}",
                details={"path": str(path), "line": e.lineno, "col": e.colno},
            ) from e

    def write_json(self, path: str | Path, data: dict) -> None:
        """
        Write data as formatted JSON.

        Args:
            path: Output file path.
            data: Data to serialize.

        Raises:
            ServiceError: If path is unsafe or write fails.
        """
        text = json.dumps(data, indent=2, ensure_ascii=False)
        self.write_text(path, text)

    # ── File Info ──────────────────────────────────────

    def exists(self, path: str | Path) -> bool:
        """
        Check if a path exists (file or directory).

        Args:
            path: Path to check.

        Returns:
            True if the path exists.

        Raises:
            ServiceError: If path is unsafe.
        """
        safe_path = self._validate_path(path)
        return safe_path.exists()

    def get_size_mb(self, path: str | Path) -> float:
        """
        Get the total size of a file or directory in megabytes.

        Args:
            path: File or directory path.

        Returns:
            Size in MB (rounded to 2 decimal places).

        Raises:
            ServiceError: If path is unsafe or doesn't exist.
        """
        safe_path = self._validate_path(path)
        if not safe_path.exists():
            return 0.0

        if safe_path.is_file():
            return round(safe_path.stat().st_size / (1024**2), 2)
        else:
            total = sum(
                f.stat().st_size
                for f in safe_path.rglob("*")
                if f.is_file()
            )
            return round(total / (1024**2), 2)

    # ── Delete ─────────────────────────────────────────

    def delete(self, path: str | Path) -> None:
        """
        Delete a file or directory (recursively).

        WARNING: This is permanent. Consider implementing a "trash" system.

        Args:
            path: File or directory to delete.

        Raises:
            ServiceError: If path is unsafe or deletion fails.
        """
        safe_path = self._validate_path(path)
        if not safe_path.exists():
            logger.debug("Nothing to delete: %s (does not exist)", safe_path)
            return

        try:
            if safe_path.is_dir():
                shutil.rmtree(safe_path)
            else:
                safe_path.unlink()
            logger.info("Deleted: %s", safe_path)
        except Exception as e:
            raise ServiceError(
                f"Failed to delete {path}: {e}",
                details={"path": str(safe_path)},
            ) from e

    def __repr__(self) -> str:
        return f"FileSystemService(allowed_root={self._allowed_root})"
