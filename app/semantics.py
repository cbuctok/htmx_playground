"""Column semantics detection."""
import re
from typing import Optional

from app.database import get_db_manager
from app.introspection import get_all_tables, introspect_table


# Semantic type patterns
SEMANTIC_PATTERNS = {
    'created_at': [
        r'^created[-_]?at$',
        r'^created[-_]?on$',
        r'^createdat$',
        r'^createdon$',
        r'^date[-_]?created$',
        r'^creation[-_]?date$',
        r'^created$',
    ],
    'updated_at': [
        r'^updated[-_]?at$',
        r'^updated[-_]?on$',
        r'^updatedat$',
        r'^updatedon$',
        r'^modified[-_]?at$',
        r'^modified[-_]?on$',
        r'^modifiedat$',
        r'^modifiedon$',
        r'^date[-_]?updated$',
        r'^date[-_]?modified$',
        r'^last[-_]?modified$',
        r'^last[-_]?updated$',
    ],
    'deleted_at': [
        r'^deleted[-_]?at$',
        r'^deleted[-_]?on$',
        r'^deletedat$',
        r'^deletedon$',
        r'^date[-_]?deleted$',
        r'^soft[-_]?deleted$',
    ],
    'created_by': [
        r'^created[-_]?by$',
        r'^createdby$',
        r'^author$',
        r'^creator$',
        r'^owner$',
    ],
    'updated_by': [
        r'^updated[-_]?by$',
        r'^updatedby$',
        r'^modified[-_]?by$',
        r'^modifiedby$',
        r'^last[-_]?modified[-_]?by$',
        r'^editor$',
    ],
    'status': [
        r'^status$',
        r'^state$',
        r'^is[-_]?active$',
        r'^active$',
        r'^enabled$',
        r'^is[-_]?enabled$',
    ],
}


def normalize_column_name(name: str) -> str:
    """Normalize column name for pattern matching."""
    return name.lower().replace('_', '').replace('-', '')


def detect_semantic_type(column_name: str) -> Optional[str]:
    """
    Detect the semantic type of a column based on its name.

    Returns:
        Semantic type string or None if not detected
    """
    normalized = column_name.lower()

    for semantic_type, patterns in SEMANTIC_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, normalized, re.IGNORECASE):
                return semantic_type

    return None


def analyze_table_semantics(table_name: str) -> dict[str, str]:
    """
    Analyze a table and detect column semantics.

    Returns:
        Dict mapping column names to their semantic types
    """
    table_info = introspect_table(table_name)
    semantics = {}

    for column in table_info.columns:
        semantic_type = detect_semantic_type(column.name)
        if semantic_type:
            semantics[column.name] = semantic_type

    return semantics


def cache_column_semantics():
    """Detect and cache column semantics for all tables."""
    db = get_db_manager()
    tables = get_all_tables()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        # Clear existing semantics
        cursor.execute("DELETE FROM column_semantics")

        # Analyze each table
        for table_name in tables:
            semantics = analyze_table_semantics(table_name)

            for column_name, semantic_type in semantics.items():
                cursor.execute(
                    "INSERT INTO column_semantics (table_name, column_name, semantic_type) "
                    "VALUES (?, ?, ?)",
                    (table_name, column_name, semantic_type)
                )

        conn.commit()


def get_table_semantics(table_name: str) -> dict[str, str]:
    """Get cached column semantics for a table."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT column_name, semantic_type FROM column_semantics WHERE table_name = ?",
            (table_name,)
        )
        return {row['column_name']: row['semantic_type'] for row in cursor.fetchall()}


def get_all_semantics() -> dict[str, dict[str, str]]:
    """Get all cached column semantics."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT table_name, column_name, semantic_type FROM column_semantics")

        result = {}
        for row in cursor.fetchall():
            table = row['table_name']
            if table not in result:
                result[table] = {}
            result[table][row['column_name']] = row['semantic_type']

        return result


def is_auto_timestamp_column(column_name: str, semantics: dict[str, str]) -> bool:
    """Check if a column should have auto-timestamp behavior."""
    semantic_type = semantics.get(column_name)
    return semantic_type in ('created_at', 'updated_at')


def is_auto_user_column(column_name: str, semantics: dict[str, str]) -> bool:
    """Check if a column should have auto-user behavior."""
    semantic_type = semantics.get(column_name)
    return semantic_type in ('created_by', 'updated_by')


def supports_soft_delete(table_name: str) -> bool:
    """Check if a table supports soft delete."""
    semantics = get_table_semantics(table_name)
    return any(s == 'deleted_at' for s in semantics.values())


def get_soft_delete_column(table_name: str) -> Optional[str]:
    """Get the soft delete column name if it exists."""
    semantics = get_table_semantics(table_name)
    for col, sem_type in semantics.items():
        if sem_type == 'deleted_at':
            return col
    return None
