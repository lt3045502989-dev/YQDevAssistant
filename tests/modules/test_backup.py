"""
Tests for the Backup module.
"""

import pytest
from pathlib import Path
from src.modules.backup.module import BackupModule
from src.modules.backup.backup_manager import BackupManager, TRACKED_FILES, BackupItem


class TestBackupManager:
    """Tests for BackupManager core logic."""

    @pytest.fixture
    def manager(self, tmp_path):
        """A BackupManager pointed at a temp directory."""
        return BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

    @pytest.fixture
    def home_with_files(self, tmp_path):
        """Create a home directory with some test config files."""
        # Create some test files
        (tmp_path / ".bashrc").write_text("alias test='echo hello'")
        (tmp_path / ".gitconfig").write_text("[user]\nname=test")
        (tmp_path / ".claude.json").write_text('{"key":"value"}')
        return tmp_path

    def test_check_files_empty_home(self, manager):
        """Empty home should find no files."""
        existing, missing = manager.check_files()
        assert len(existing) == 0
        # All tracked files should be missing
        assert len(missing) > 0

    def test_check_files_with_files(self, tmp_path):
        """Home with .bashrc should find it."""
        (tmp_path / ".bashrc").write_text("test")
        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )
        existing, missing = mgr.check_files()
        assert ".bashrc" in existing

    def test_create_backup(self, tmp_path):
        """create_backup() copies files and returns a BackupItem."""
        (tmp_path / ".bashrc").write_text("alias test='hello'")
        (tmp_path / ".gitconfig").write_text("[user]\nname=test")

        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

        item = mgr.create_backup()
        assert item.file_count >= 2
        assert item.id  # Has a valid backup ID
        assert (mgr._backups_dir / item.id).exists()

        # Verify files were copied
        assert (mgr._backups_dir / item.id / ".bashrc").exists()
        assert (mgr._backups_dir / item.id / "manifest.json").exists()

    def test_list_backups(self, tmp_path):
        """list_backups() returns BackupItems sorted newest first."""
        (tmp_path / ".bashrc").write_text("test")
        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

        mgr.create_backup()
        mgr.create_backup()

        backups = mgr.list_backups()
        assert len(backups) == 2
        # Newest first
        assert backups[0].timestamp >= backups[1].timestamp

    def test_restore_creates_safety_backup(self, tmp_path):
        """restore_backup() creates a safety backup before restoring."""
        (tmp_path / ".bashrc").write_text("original")
        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

        original_backup = mgr.create_backup()

        # Modify the file
        (tmp_path / ".bashrc").write_text("modified")

        # Restore from the backup
        safety = mgr.restore_backup(original_backup.id)

        # File should be restored to "original"
        assert (tmp_path / ".bashrc").read_text() == "original"

        # Safety backup should exist with "modified" content
        safety_path = mgr._backups_dir / safety.id
        assert safety_path.exists()
        safety_file = safety_path / ".bashrc"
        if safety_file.exists():
            assert safety_file.read_text() == "modified"

    def test_restore_nonexistent_raises(self, manager):
        """Restoring a nonexistent backup raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            manager.restore_backup("nonexistent_backup")

    def test_delete_backup(self, tmp_path):
        """delete_backup() removes a backup directory."""
        (tmp_path / ".bashrc").write_text("test")
        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

        item = mgr.create_backup()
        assert (mgr._backups_dir / item.id).exists()

        mgr.delete_backup(item.id)
        assert not (mgr._backups_dir / item.id).exists()

    def test_cleanup_old_backups(self, tmp_path):
        """cleanup_old_backups() keeps only the most recent N."""
        (tmp_path / ".bashrc").write_text("test")
        mgr = BackupManager(
            backups_dir=str(tmp_path / "backups"),
            home_dir=str(tmp_path),
        )

        # Create 5 backups
        for _ in range(5):
            mgr.create_backup()

        assert len(mgr.list_backups()) == 5

        # Keep only 2
        deleted = mgr.cleanup_old_backups(keep=2)
        assert deleted == 3
        assert len(mgr.list_backups()) == 2

    def test_tracked_files_list(self):
        """TRACKED_FILES should have sensible entries."""
        assert len(TRACKED_FILES) > 0
        # Each entry should be (path, description)
        for entry in TRACKED_FILES:
            assert len(entry) == 2
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], str)


class TestBackupModule:
    """Tests for BackupModule (integration with BaseModule)."""

    def test_info(self):
        mod = BackupModule()
        assert mod.info.name == "backup"
        assert mod.info.category == "maintenance"

    def test_check(self):
        mod = BackupModule()
        result = mod.check()
        assert result.is_ok
        assert result.data is not None
        assert "existing" in result.data
        assert "missing" in result.data

    def test_execute_list(self):
        mod = BackupModule()
        result = mod.execute(action="list")
        assert result.is_ok
        assert result.data["action"] == "list"

    def test_execute_backup_and_restore(self, tmp_path):
        """Integration: create a backup, list it, restore it."""
        # Create a test file
        (tmp_path / ".bashrc").write_text("test content")

        mod = BackupModule(config={
            "home_dir": str(tmp_path),
            "backups_dir": str(tmp_path / "test_backups"),
        })

        # Create backup
        r = mod.execute(action="backup")
        assert r.is_ok
        backup_id = r.data["backup_id"]

        # List should show it
        r2 = mod.execute(action="list")
        assert r2.data["count"] == 1

        # Modify the file
        (tmp_path / ".bashrc").write_text("changed")

        # Restore
        r3 = mod.execute(action="restore", backup_id=backup_id)
        assert r3.is_ok
        assert (tmp_path / ".bashrc").read_text() == "test content"

    def test_execute_unknown_action(self):
        mod = BackupModule()
        result = mod.execute(action="invalid_action")
        assert not result.is_ok
        assert "Unknown action" in result.errors[0]

    def test_execute_restore_without_id(self):
        mod = BackupModule()
        result = mod.execute(action="restore")
        assert not result.is_ok
        assert "backup_id" in result.errors[0]

    def test_get_status(self):
        mod = BackupModule()
        status = mod.get_status()
        assert "backup_ready" in status
        assert "backups" in status
