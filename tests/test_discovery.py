"""Tests for the discovery module."""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app.discovery import (
    DatabaseDiscoveryError,
    discover_target_database,
    load_target_database,
    switch_target_database,
    get_available_databases,
)
from app.database import DatabaseManager


class TestDatabaseDiscoveryError:
    """Tests for DatabaseDiscoveryError exception."""

    def test_is_exception(self):
        """Should be an Exception subclass."""
        assert issubclass(DatabaseDiscoveryError, Exception)

    def test_can_be_raised_with_message(self):
        """Should accept a message."""
        with pytest.raises(DatabaseDiscoveryError, match="test message"):
            raise DatabaseDiscoveryError("test message")


class TestDiscoverTargetDatabase:
    """Tests for discover_target_database function."""

    def test_raises_error_when_no_db_files(self, temp_dir):
        """Should raise error when no .db files found."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            with pytest.raises(DatabaseDiscoveryError, match="No target database found"):
                discover_target_database()

    def test_discovers_single_database(self, temp_dir):
        """Should discover a single database."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create a database file
        db_path = upload_dir / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            path, name, multiple, available = discover_target_database()

        assert path == db_path
        assert name == "test.db"
        assert multiple is False
        assert available == ["test.db"]

    def test_discovers_multiple_databases(self, temp_dir):
        """Should discover multiple databases and select most recent."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create multiple database files
        import time
        db1_path = upload_dir / "old.db"
        conn = sqlite3.connect(str(db1_path))
        conn.close()

        time.sleep(0.01)  # Ensure different mtime

        db2_path = upload_dir / "new.db"
        conn = sqlite3.connect(str(db2_path))
        conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            path, name, multiple, available = discover_target_database()

        assert name == "new.db"  # Most recent
        assert multiple is True
        assert len(available) == 2
        assert "old.db" in available
        assert "new.db" in available

    def test_ignores_system_db(self, temp_dir):
        """Should ignore system.db."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create system.db
        system_path = upload_dir / "system.db"
        conn = sqlite3.connect(str(system_path))
        conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir), \
             patch("app.discovery.SYSTEM_DB_NAME", "system.db"):
            with pytest.raises(DatabaseDiscoveryError):
                discover_target_database()


class TestLoadTargetDatabase:
    """Tests for load_target_database function."""

    def test_loads_database_into_manager(self, temp_dir, reset_database_manager):
        """Should load database into manager."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        db_path = upload_dir / "target.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            db_name, multiple, available = load_target_database()

        assert db_name == "target.db"
        assert multiple is False

        manager = DatabaseManager.get_instance()
        assert manager.target_db_path == db_path
        assert manager.target_db_name == "target.db"

    def test_sets_multiple_flag(self, temp_dir, reset_database_manager):
        """Should set multiple_dbs_detected flag."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        import time
        for name in ["db1.db", "db2.db"]:
            db_path = upload_dir / name
            conn = sqlite3.connect(str(db_path))
            conn.close()
            time.sleep(0.01)

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            _, multiple, available = load_target_database()

        assert multiple is True

        manager = DatabaseManager.get_instance()
        assert manager.multiple_dbs_detected is True
        assert len(manager.available_dbs) == 2


class TestSwitchTargetDatabase:
    """Tests for switch_target_database function."""

    def test_switches_to_valid_database(self, temp_dir, reset_database_manager):
        """Should switch to a valid database."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create two databases
        db1_path = upload_dir / "db1.db"
        db2_path = upload_dir / "db2.db"
        for path in [db1_path, db2_path]:
            conn = sqlite3.connect(str(path))
            conn.close()

        # Set up manager with first database
        manager = DatabaseManager.get_instance()
        manager.set_target_db(db1_path, "db1.db")

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            result = switch_target_database("db2.db")

        assert result is True
        assert manager.target_db_path == db2_path
        assert manager.target_db_name == "db2.db"

    def test_returns_false_for_nonexistent_database(self, temp_dir, reset_database_manager):
        """Should return False for nonexistent database."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            result = switch_target_database("nonexistent.db")

        assert result is False

    def test_rejects_system_db(self, temp_dir, reset_database_manager):
        """Should reject switching to system.db."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create system.db
        system_path = upload_dir / "system.db"
        conn = sqlite3.connect(str(system_path))
        conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir), \
             patch("app.discovery.SYSTEM_DB_NAME", "system.db"):
            result = switch_target_database("system.db")

        assert result is False


class TestGetAvailableDatabases:
    """Tests for get_available_databases function."""

    def test_returns_list_of_databases(self, temp_dir):
        """Should return list of available databases."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create databases
        for name in ["alpha.db", "beta.db", "gamma.db"]:
            db_path = upload_dir / name
            conn = sqlite3.connect(str(db_path))
            conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            available = get_available_databases()

        assert len(available) == 3
        assert "alpha.db" in available
        assert "beta.db" in available
        assert "gamma.db" in available

    def test_returns_sorted_list(self, temp_dir):
        """Should return sorted list."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        for name in ["z.db", "a.db", "m.db"]:
            db_path = upload_dir / name
            conn = sqlite3.connect(str(db_path))
            conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            available = get_available_databases()

        assert available == sorted(available)

    def test_excludes_system_db(self, temp_dir):
        """Should exclude system.db."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        for name in ["target.db", "system.db"]:
            db_path = upload_dir / name
            conn = sqlite3.connect(str(db_path))
            conn.close()

        with patch("app.discovery.UPLOAD_DIR", upload_dir), \
             patch("app.discovery.SYSTEM_DB_NAME", "system.db"):
            available = get_available_databases()

        assert "system.db" not in available
        assert "target.db" in available

    def test_returns_empty_for_no_databases(self, temp_dir):
        """Should return empty list when no databases exist."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            available = get_available_databases()

        assert available == []

    def test_ignores_non_db_files(self, temp_dir):
        """Should ignore non-.db files."""
        upload_dir = temp_dir / "uploaded_db"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create various files
        (upload_dir / "test.db").touch()
        (upload_dir / "readme.txt").touch()
        (upload_dir / "data.json").touch()
        (upload_dir / "backup.db.bak").touch()

        with patch("app.discovery.UPLOAD_DIR", upload_dir):
            available = get_available_databases()

        assert available == ["test.db"]
