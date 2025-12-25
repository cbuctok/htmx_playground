"""Tests for the database module."""
import sqlite3
from pathlib import Path

import pytest

from app.database import DatabaseManager, get_db_manager, init_system_db


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    def test_singleton_pattern(self, reset_database_manager):
        """DatabaseManager should use singleton pattern."""
        manager1 = DatabaseManager.get_instance()
        manager2 = DatabaseManager.get_instance()
        assert manager1 is manager2

    def test_initial_state(self, reset_database_manager):
        """DatabaseManager should have correct initial state."""
        manager = DatabaseManager.get_instance()
        assert manager.target_db_path is None
        assert manager.target_db_name is None
        assert manager.multiple_dbs_detected is False
        assert manager.available_dbs == []

    def test_set_target_db(self, db_manager: DatabaseManager, target_db_path: Path):
        """set_target_db should configure target database."""
        assert db_manager.target_db_path == target_db_path
        assert db_manager.target_db_name == target_db_path.name

    def test_clear_target_db(self, db_manager: DatabaseManager):
        """clear_target_db should reset target database configuration."""
        db_manager.clear_target_db()
        assert db_manager.target_db_path is None
        assert db_manager.target_db_name is None

    def test_get_system_connection(self, db_manager: DatabaseManager):
        """get_system_connection should return a working connection."""
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (1)")
            conn.commit()
            cursor.execute("SELECT * FROM test")
            assert cursor.fetchone()[0] == 1

    def test_get_target_connection(self, db_manager: DatabaseManager):
        """get_target_connection should return a working connection."""
        with db_manager.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test_target (id INTEGER)")
            cursor.execute("INSERT INTO test_target VALUES (42)")
            conn.commit()
            cursor.execute("SELECT * FROM test_target")
            assert cursor.fetchone()[0] == 42

    def test_get_target_connection_no_db(self, reset_database_manager, system_db_path: Path):
        """get_target_connection should raise error when no target is set."""
        manager = DatabaseManager.get_instance()
        manager.system_db_path = system_db_path

        with pytest.raises(RuntimeError, match="No target database loaded"):
            with manager.get_target_connection():
                pass

    def test_connection_row_factory(self, db_manager: DatabaseManager):
        """Connections should have sqlite3.Row as row_factory."""
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (name TEXT)")
            cursor.execute("INSERT INTO test VALUES ('test')")
            conn.commit()
            cursor.execute("SELECT * FROM test")
            row = cursor.fetchone()
            assert row['name'] == 'test'

    def test_connection_cleanup(self, db_manager: DatabaseManager):
        """Connections should be closed after context manager exits."""
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE cleanup_test (id INTEGER)")
            conn.commit()

        # Connection should be closed, but database should persist
        with db_manager.get_system_connection() as conn2:
            cursor = conn2.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cleanup_test'")
            assert cursor.fetchone() is not None


class TestGetDbManager:
    """Tests for get_db_manager function."""

    def test_returns_singleton(self, reset_database_manager):
        """get_db_manager should return the singleton instance."""
        manager1 = get_db_manager()
        manager2 = get_db_manager()
        assert manager1 is manager2

    def test_returns_database_manager_instance(self, reset_database_manager):
        """get_db_manager should return a DatabaseManager instance."""
        manager = get_db_manager()
        assert isinstance(manager, DatabaseManager)


class TestInitSystemDb:
    """Tests for init_system_db function."""

    def test_creates_users_table(self, db_manager: DatabaseManager):
        """init_system_db should create users table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            assert cursor.fetchone() is not None

    def test_creates_dashboards_table(self, db_manager: DatabaseManager):
        """init_system_db should create dashboards table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboards'")
            assert cursor.fetchone() is not None

    def test_creates_views_table(self, db_manager: DatabaseManager):
        """init_system_db should create views table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='views'")
            assert cursor.fetchone() is not None

    def test_creates_column_semantics_table(self, db_manager: DatabaseManager):
        """init_system_db should create column_semantics table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='column_semantics'")
            assert cursor.fetchone() is not None

    def test_creates_app_config_table(self, db_manager: DatabaseManager):
        """init_system_db should create app_config table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_config'")
            assert cursor.fetchone() is not None

    def test_creates_ui_preferences_table(self, db_manager: DatabaseManager):
        """init_system_db should create ui_preferences table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ui_preferences'")
            assert cursor.fetchone() is not None

    def test_creates_table_metadata_table(self, db_manager: DatabaseManager):
        """init_system_db should create table_metadata table."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='table_metadata'")
            assert cursor.fetchone() is not None

    def test_seeds_default_users(self, db_manager: DatabaseManager):
        """init_system_db should seed default users."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM users ORDER BY username")
            users = cursor.fetchall()
            usernames = [u['username'] for u in users]
            assert 'admin' in usernames
            assert 'user1' in usernames
            assert 'user2' in usernames

    def test_admin_has_admin_role(self, db_manager: DatabaseManager):
        """init_system_db should set admin role correctly."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE username = 'admin'")
            assert cursor.fetchone()['role'] == 'admin'

    def test_seeds_default_app_config(self, db_manager: DatabaseManager):
        """init_system_db should seed default app config."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_config WHERE key = 'app_name'")
            row = cursor.fetchone()
            assert row is not None
            assert row['value'] == 'SQLite Admin'

    def test_seeds_default_ui_preferences(self, db_manager: DatabaseManager):
        """init_system_db should seed default UI preferences."""
        init_system_db()
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM ui_preferences WHERE key = 'page_size'")
            row = cursor.fetchone()
            assert row is not None
            assert row['value'] == '25'

    def test_idempotent_table_creation(self, db_manager: DatabaseManager):
        """init_system_db should be idempotent for table creation."""
        init_system_db()
        init_system_db()  # Call again - should not raise
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            # Should have the expected number of tables
            assert cursor.fetchone()[0] >= 7

    def test_does_not_duplicate_users(self, db_manager: DatabaseManager):
        """init_system_db should not duplicate users on second call."""
        init_system_db()
        init_system_db()  # Call again
        with db_manager.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            assert count == 3  # Only 3 default users
