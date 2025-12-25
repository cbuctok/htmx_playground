"""Pytest fixtures for the test suite."""
import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import DatabaseManager


@pytest.fixture(autouse=True)
def reset_database_manager():
    """Reset the DatabaseManager singleton before each test."""
    DatabaseManager._instance = None
    yield
    DatabaseManager._instance = None


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def system_db_path(temp_dir: Path) -> Path:
    """Create a path for a temporary system database."""
    return temp_dir / "system.db"


@pytest.fixture
def target_db_path(temp_dir: Path) -> Path:
    """Create a path for a temporary target database."""
    upload_dir = temp_dir / "uploaded_db"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / "test_target.db"


@pytest.fixture
def db_manager(system_db_path: Path, target_db_path: Path) -> DatabaseManager:
    """Create a DatabaseManager with temporary databases."""
    # Create the target database file
    conn = sqlite3.connect(str(target_db_path))
    conn.close()

    # Create and configure the manager
    manager = DatabaseManager.get_instance()
    manager.system_db_path = system_db_path
    manager.set_target_db(target_db_path, target_db_path.name)

    return manager


@pytest.fixture
def initialized_system_db(db_manager: DatabaseManager) -> DatabaseManager:
    """Create a DatabaseManager with initialized system database."""
    with db_manager.get_system_connection() as conn:
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

        # Seed default users
        default_users = [
            ('admin', 'password', 'admin'),
            ('user1', 'password', 'user'),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            default_users
        )

        conn.commit()

    return db_manager


@pytest.fixture
def sample_target_db(db_manager: DatabaseManager) -> DatabaseManager:
    """Create a target database with sample tables."""
    with db_manager.get_target_connection() as conn:
        cursor = conn.cursor()

        # Products table
        cursor.execute('''
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0,
                category_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')

        # Categories table
        cursor.execute('''
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT
            )
        ''')

        # Tasks table (with soft delete)
        cursor.execute('''
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'todo',
                assigned_to TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                deleted_at TEXT
            )
        ''')

        # Users table (for audit columns)
        cursor.execute('''
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                author TEXT,
                editor TEXT,
                created_at TEXT,
                modified_at TEXT
            )
        ''')

        # Insert sample data
        cursor.execute(
            "INSERT INTO categories (name, description, created_at) VALUES (?, ?, ?)",
            ("Electronics", "Electronic devices", "2024-01-01 00:00:00")
        )
        cursor.execute(
            "INSERT INTO products (name, price, category_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("Test Product", 29.99, 1, "2024-01-01 00:00:00", "2024-01-01 00:00:00")
        )
        cursor.execute(
            "INSERT INTO tasks (title, priority, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("Test Task", "high", "2024-01-01 00:00:00", "2024-01-01 00:00:00")
        )

        conn.commit()

    return db_manager


@pytest.fixture
def full_test_setup(initialized_system_db: DatabaseManager, sample_target_db: DatabaseManager) -> DatabaseManager:
    """Complete test setup with both system and target databases initialized."""
    # Cache column semantics in system db
    with initialized_system_db.get_system_connection() as conn:
        cursor = conn.cursor()
        semantics = [
            ("products", "created_at", "created_at"),
            ("products", "updated_at", "updated_at"),
            ("tasks", "created_at", "created_at"),
            ("tasks", "updated_at", "updated_at"),
            ("tasks", "deleted_at", "deleted_at"),
            ("tasks", "created_by", "created_by"),
            ("employees", "created_at", "created_at"),
            ("employees", "modified_at", "updated_at"),
            ("employees", "author", "created_by"),
            ("employees", "editor", "updated_by"),
        ]
        cursor.executemany(
            "INSERT OR REPLACE INTO column_semantics (table_name, column_name, semantic_type) VALUES (?, ?, ?)",
            semantics
        )
        conn.commit()

    return initialized_system_db
