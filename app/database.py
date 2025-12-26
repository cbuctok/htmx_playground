"""Database connection and management."""
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from app.config import SYSTEM_DB_PATH


class DatabaseManager:
    """Manages connections to system and target databases."""

    _instance: Optional['DatabaseManager'] = None

    def __init__(self):
        self.system_db_path = SYSTEM_DB_PATH
        self.target_db_path: Optional[Path] = None
        self.target_db_name: Optional[str] = None
        self.multiple_dbs_detected: bool = False
        self.available_dbs: list[str] = []

    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @contextmanager
    def get_system_connection(self):
        """Get a connection to the system database."""
        conn = sqlite3.connect(str(self.system_db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_target_connection(self):
        """Get a connection to the target database."""
        if self.target_db_path is None:
            raise RuntimeError("No target database loaded")
        conn = sqlite3.connect(str(self.target_db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def set_target_db(self, path: Path, name: str):
        """Set the target database."""
        self.target_db_path = path
        self.target_db_name = name

    def clear_target_db(self):
        """Clear target database reference."""
        self.target_db_path = None
        self.target_db_name = None


def get_db_manager() -> DatabaseManager:
    """Get the database manager singleton."""
    return DatabaseManager.get_instance()


def init_system_db():
    """Initialize the system database with required tables."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
        ''')

        # Dashboards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dashboards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}'
            )
        ''')

        # Views table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sql TEXT NOT NULL,
                source_table TEXT
            )
        ''')

        # Column semantics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS column_semantics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                semantic_type TEXT NOT NULL,
                UNIQUE(table_name, column_name)
            )
        ''')

        # App config table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # UI preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ui_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Table metadata cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS table_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT UNIQUE NOT NULL,
                row_count INTEGER DEFAULT 0,
                columns_json TEXT NOT NULL DEFAULT '[]',
                foreign_keys_json TEXT NOT NULL DEFAULT '[]'
            )
        ''')

        # Table dependencies (for Story Mode)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS table_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_table TEXT NOT NULL,
                to_table TEXT NOT NULL,
                UNIQUE(from_table, to_table)
            )
        ''')

        # Story steps (for Story Mode)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS story_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'table',
                source_name TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                min_records_required INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        ''')

        conn.commit()

        # Seed default users if not exist
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_users = [
                ('admin', 'password', 'admin'),
                ('user1', 'password', 'user'),
                ('user2', 'password', 'user'),
            ]
            cursor.executemany(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                default_users
            )
            conn.commit()

        # Seed default app config if not exist
        cursor.execute("SELECT COUNT(*) FROM app_config")
        if cursor.fetchone()[0] == 0:
            default_config = [
                ('app_name', 'SQLite Admin'),
                ('logo_path', ''),
                ('primary_color', '#3b82f6'),
                ('secondary_color', '#64748b'),
                ('background_color', '#f8fafc'),
                ('accent_color', '#10b981'),
                ('story_mode_enabled', 'false'),
            ]
            cursor.executemany(
                "INSERT INTO app_config (key, value) VALUES (?, ?)",
                default_config
            )
            conn.commit()

        # Ensure story_mode_enabled exists (migration for existing databases)
        cursor.execute("SELECT value FROM app_config WHERE key = 'story_mode_enabled'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO app_config (key, value) VALUES ('story_mode_enabled', 'false')"
            )
            conn.commit()

        # Seed default UI preferences if not exist
        cursor.execute("SELECT COUNT(*) FROM ui_preferences")
        if cursor.fetchone()[0] == 0:
            default_prefs = [
                ('date_format', '%Y-%m-%d %H:%M:%S'),
                ('page_size', '25'),
                ('theme', 'light'),
            ]
            cursor.executemany(
                "INSERT INTO ui_preferences (key, value) VALUES (?, ?)",
                default_prefs
            )
            conn.commit()
