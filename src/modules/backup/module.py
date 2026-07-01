"""
Backup Module — development environment configuration backup.

Backs up:
    - Shell & Git configs (.bashrc, .gitconfig, .npmrc, etc.)
    - Claude Code configs (.claude.json, settings.json)
    - Development scripts and documentation
    - Codex CLI config

Usage:
    # CLI
    yqa check backup              # Check what can be backed up
    yqa run backup action=backup  # Create a backup
    yqa run backup action=list    # List backups
    yqa run backup action=restore backup_id=2026-07-01_14-30-00  # Restore
    yqa run backup action=cleanup keep=10  # Keep last 10 backups

    # Python
    python -m src.modules.backup

Safety:
    - Restore ALWAYS creates a safety backup first
    - All operations are constrained to C:/Users/L1372
"""

from src.core.module_base import BaseModule, ModuleResult, ModuleInfo
from src.modules.backup.backup_manager import BackupManager, TRACKED_FILES


class BackupModule(BaseModule):
    """
    Development environment backup and restore.

    check() — verify which files exist/can be backed up
    execute() — perform backup, restore, list, or cleanup actions
    """

    info = ModuleInfo(
        name="backup",
        version="0.1.0",
        description="开发环境配置备份 — 备份/还原/管理配置文件",
        category="maintenance",
        icon="💾",
    )

    def __init__(self, config=None, event_bus=None):
        super().__init__(config, event_bus)
        home = self.config.get("home_dir", "C:/Users/L1372")
        backups = self.config.get("backups_dir", "backups")
        self._manager = BackupManager(backups_dir=backups, home_dir=home)

    # ── check(): what can be backed up? ─────────────────

    def check(self) -> ModuleResult:
        """
        Check the state of tracked files.

        Returns:
            ModuleResult with data = {
                "existing": [...],  # files that exist (can be backed up)
                "missing": [...],   # files that don't exist
                "backups": [...],   # existing backups
            }
        """
        try:
            existing, missing = self._manager.check_files()
            backups = self._manager.list_backups()

            data = {
                "existing": existing,
                "missing": missing,
                "total_tracked": len(TRACKED_FILES),
                "existing_count": len(existing),
                "missing_count": len(missing),
                "backups_count": len(backups),
                "backups": [
                    {
                        "id": b.id,
                        "timestamp": b.timestamp.strftime("%Y-%m-%d %H:%M"),
                        "file_count": b.file_count,
                        "size_mb": b.total_size_mb,
                    }
                    for b in backups[:5]  # Show last 5
                ],
            }

            warnings = []
            if missing:
                warnings.append(
                    f"{len(missing)} tracked file(s) not found: "
                    + ", ".join(missing[:5])
                    + ("..." if len(missing) > 5 else "")
                )

            return ModuleResult.ok(self.info.name, data, warnings)

        except Exception as e:
            return ModuleResult.fail(self.info.name, [str(e)])

    # ── execute(): backup, restore, list, cleanup ────────

    def execute(self, **kwargs) -> ModuleResult:
        """
        Perform backup operations.

        Actions:
            backup  — create a new backup
            list    — list all backups
            restore — restore from a specific backup
            cleanup — delete old backups

        Args:
            action: "backup" (default), "list", "restore", "cleanup"
            backup_id: Required for restore action
            keep: Number of backups to keep (for cleanup, default 10)
        """
        action = kwargs.get("action", "backup")

        try:
            if action == "backup":
                return self._do_backup()
            elif action == "list":
                return self._do_list()
            elif action == "restore":
                backup_id = kwargs.get("backup_id")
                if not backup_id:
                    return ModuleResult.fail(
                        self.info.name,
                        ["backup_id is required for restore action. "
                         "Example: yqa run backup action=restore backup_id=2026-07-01_14-30-00"],
                    )
                return self._do_restore(backup_id)
            elif action == "cleanup":
                keep = int(kwargs.get("keep", 10))
                return self._do_cleanup(keep)
            else:
                return ModuleResult.fail(
                    self.info.name,
                    [f"Unknown action: {action}. Valid: backup, list, restore, cleanup"],
                )
        except Exception as e:
            return ModuleResult.fail(self.info.name, [str(e)])

    # ── Action Handlers ─────────────────────────────────

    def _do_backup(self) -> ModuleResult:
        item = self._manager.create_backup()
        return ModuleResult.ok(
            self.info.name,
            {
                "action": "backup",
                "backup_id": item.id,
                "file_count": item.file_count,
                "size_mb": item.total_size_mb,
                "files": item.files,
            },
        )

    def _do_list(self) -> ModuleResult:
        backups = self._manager.list_backups()
        return ModuleResult.ok(
            self.info.name,
            {
                "action": "list",
                "count": len(backups),
                "backups": [
                    {
                        "id": b.id,
                        "timestamp": b.timestamp.strftime("%Y-%m-%d %H:%M"),
                        "file_count": b.file_count,
                        "size_mb": b.total_size_mb,
                        "files": b.files[:10],
                    }
                    for b in backups
                ],
            },
        )

    def _do_restore(self, backup_id: str) -> ModuleResult:
        safety = self._manager.restore_backup(backup_id)
        return ModuleResult.ok(
            self.info.name,
            {
                "action": "restore",
                "restored_from": backup_id,
                "safety_backup_id": safety.id,
                "note": "Current files were backed up to the safety backup before restore.",
            },
        )

    def _do_cleanup(self, keep: int) -> ModuleResult:
        deleted = self._manager.cleanup_old_backups(keep)
        return ModuleResult.ok(
            self.info.name,
            {
                "action": "cleanup",
                "deleted": deleted,
                "kept": keep,
            },
        )

    # ── Status ──────────────────────────────────────────

    def get_status(self) -> dict:
        status = super().get_status()
        try:
            existing, _ = self._manager.check_files()
            backups = self._manager.list_backups()
            status["backup_ready"] = len(existing)
            status["backups"] = len(backups)
        except Exception:
            status["backup_ready"] = "error"
        return status
