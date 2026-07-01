"""
Backup Manager — core logic for backing up and restoring dev environment files.

Design:
    - Backups are timestamped directories: backups/2026-07-01_14-30-00/
    - Each backup contains copies of tracked config files
    - A manifest.json records what was backed up and when
    - Restore creates a safety backup of current state first
"""

import json
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

from src.services.filesystem_service import FileSystemService


# ── Backup Item ─────────────────────────────────────────────


@dataclass
class BackupItem:
    """Information about a single backup."""

    id: str  # e.g., "2026-07-01_14-30-00"
    path: Path
    timestamp: datetime
    file_count: int = 0
    total_size_mb: float = 0.0
    files: list[str] = field(default_factory=list)


# ── Tracked Files ───────────────────────────────────────────

# Files to back up: (source_path, description)
TRACKED_FILES = [
    # Shell & Git
    (".bashrc", "Bash shell configuration"),
    (".bash_profile", "Bash profile"),
    (".gitconfig", "Git global configuration"),
    (".gitignore", "Git global ignore rules"),
    (".npmrc", "npm configuration"),
    # Claude Code
    (".claude.json", "Claude Code MCP configuration"),
    (".claude/settings.json", "Claude Code settings"),
    (".claude/settings.local.json", "Claude Code local permissions"),
    # Development Scripts
    ("Development/Scripts/dev-check.sh", "Dev environment check script"),
    ("Development/Scripts/dev-update-check.sh", "Dev tool update check script"),
    ("Development/Scripts/weekly-health.sh", "Weekly health check script"),
    ("Development/Resources/开发环境设置总结.md", "Dev environment setup summary"),
    ("Development/Resources/我的电脑说明书.md", "Computer hardware reference"),
    # Codex
    (".codex/config.toml", "Codex CLI configuration"),
]


# ── Backup Manager ──────────────────────────────────────────


class BackupManager:
    """
    Manages backup creation, listing, and restoration.

    Uses FileSystemService for safe filesystem operations.
    All paths are validated to be within the allowed root.
    """

    def __init__(
        self,
        backups_dir: str | Path = "backups",
        home_dir: str | Path = "C:/Users/L1372",
    ) -> None:
        self._backups_dir = Path(backups_dir)
        self._home_dir = Path(home_dir)
        self._fs = FileSystemService(allowed_root=str(self._home_dir))

    # ── Check ───────────────────────────────────────────

    def check_files(self) -> tuple[list[str], list[str]]:
        """
        Check which tracked files exist and which are missing.

        Returns:
            Tuple of (existing_files, missing_files).
        """
        existing = []
        missing = []

        for rel_path, _ in TRACKED_FILES:
            full_path = self._home_dir / rel_path
            if full_path.exists():
                existing.append(rel_path)
            else:
                missing.append(rel_path)

        return existing, missing

    # ── Backup ──────────────────────────────────────────

    def create_backup(self) -> BackupItem:
        """
        Create a new backup of all tracked files.

        Creates a timestamped directory and copies all existing tracked files.

        Returns:
            BackupItem describing the created backup.

        Raises:
            ServiceError: If backup creation fails.
        """
        timestamp = datetime.now(timezone.utc)
        # Include microseconds to prevent collisions when called rapidly
        backup_id = timestamp.strftime("%Y-%m-%d_%H-%M-%S-%f")
        backup_dir = self._backups_dir / backup_id

        # Ensure backup directory exists
        self._fs.ensure_dir(str(backup_dir))

        backed_up = []
        total_size = 0

        for rel_path, _ in TRACKED_FILES:
            src = self._home_dir / rel_path
            if not src.exists():
                continue

            # Preserve directory structure in backup
            dest = backup_dir / rel_path
            self._fs.ensure_dir(str(dest.parent))

            # Copy file
            shutil.copy2(str(src), str(dest))
            backed_up.append(rel_path)
            total_size += dest.stat().st_size

        # Create manifest
        manifest = {
            "id": backup_id,
            "timestamp": timestamp.isoformat(),
            "file_count": len(backed_up),
            "files": backed_up,
        }
        manifest_path = backup_dir / "manifest.json"
        self._fs.write_json(str(manifest_path), manifest)

        return BackupItem(
            id=backup_id,
            path=backup_dir,
            timestamp=timestamp,
            file_count=len(backed_up),
            total_size_mb=round(total_size / (1024**2), 2),
            files=backed_up,
        )

    # ── List ────────────────────────────────────────────

    def list_backups(self) -> list[BackupItem]:
        """
        List all available backups, sorted newest first.

        Returns:
            List of BackupItems.
        """
        if not self._backups_dir.exists():
            return []

        backups = []
        for entry in sorted(
            self._backups_dir.iterdir(), reverse=True
        ):
            if not entry.is_dir():
                continue

            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                backups.append(BackupItem(
                    id=manifest["id"],
                    path=entry,
                    timestamp=datetime.fromisoformat(manifest["timestamp"]),
                    file_count=manifest.get("file_count", 0),
                    files=manifest.get("files", []),
                    total_size_mb=round(
                        sum(
                            (entry / f).stat().st_size
                            for f in manifest.get("files", [])
                            if (entry / f).exists()
                        ) / (1024**2),
                        2,
                    ),
                ))
            except (json.JSONDecodeError, KeyError):
                continue

        return backups

    # ── Restore ─────────────────────────────────────────

    def restore_backup(self, backup_id: str) -> BackupItem:
        """
        Restore files from a backup.

        SAFETY: Creates a safety backup of current files first.

        Args:
            backup_id: The backup to restore from.

        Returns:
            BackupItem describing the safety backup.

        Raises:
            FileNotFoundError: If the backup doesn't exist.
            ServiceError: If restore fails.
        """
        backup_dir = self._backups_dir / backup_id
        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup not found: {backup_id}")

        # Safety first: back up current state
        safety = self.create_backup()

        # Restore each file from the backup
        restored = 0
        for rel_path, _ in TRACKED_FILES:
            src = backup_dir / rel_path
            if not src.exists():
                continue

            dest = self._home_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            restored += 1

        # Update safety backup manifest with restore info
        safety_manifest = backup_dir.parent / safety.id / "manifest.json"
        if safety_manifest.exists():
            manifest = json.loads(safety_manifest.read_text("utf-8"))
            manifest["note"] = f"Safety backup before restore from {backup_id}"
            safety_manifest.write_text(json.dumps(manifest, indent=2), "utf-8")

        return safety

    # ── Cleanup ─────────────────────────────────────────

    def delete_backup(self, backup_id: str) -> None:
        """
        Delete a specific backup.

        Args:
            backup_id: The backup to delete.

        Raises:
            FileNotFoundError: If the backup doesn't exist.
        """
        backup_dir = self._backups_dir / backup_id
        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup not found: {backup_id}")

        shutil.rmtree(str(backup_dir))

    def cleanup_old_backups(self, keep: int = 10) -> int:
        """
        Delete old backups, keeping only the most recent N.

        Args:
            keep: Number of recent backups to keep.

        Returns:
            Number of backups deleted.
        """
        backups = self.list_backups()
        if len(backups) <= keep:
            return 0

        deleted = 0
        for backup in backups[keep:]:
            self.delete_backup(backup.id)
            deleted += 1

        return deleted
