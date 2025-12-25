"""Schema introspection for target databases."""
import json
from dataclasses import dataclass, asdict
from typing import Optional

from app.database import get_db_manager


@dataclass
class ColumnInfo:
    """Information about a database column."""
    cid: int
    name: str
    type: str
    notnull: bool
    default_value: Optional[str]
    pk: bool


@dataclass
class ForeignKeyInfo:
    """Information about a foreign key."""
    id: int
    seq: int
    table: str
    from_col: str
    to_col: str
    on_update: str
    on_delete: str
    match: str


@dataclass
class TableInfo:
    """Information about a database table."""
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]
    row_count: int


def introspect_table(table_name: str) -> TableInfo:
    """
    Introspect a single table in the target database.

    Args:
        table_name: Name of the table to introspect

    Returns:
        TableInfo with columns, foreign keys, and row count
    """
    db = get_db_manager()

    with db.get_target_connection() as conn:
        cursor = conn.cursor()

        # Get columns via PRAGMA table_info
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = []
        for row in cursor.fetchall():
            columns.append(ColumnInfo(
                cid=row['cid'],
                name=row['name'],
                type=row['type'] or 'TEXT',
                notnull=bool(row['notnull']),
                default_value=row['dflt_value'],
                pk=bool(row['pk'])
            ))

        # Get foreign keys via PRAGMA foreign_key_list
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        foreign_keys = []
        for row in cursor.fetchall():
            foreign_keys.append(ForeignKeyInfo(
                id=row['id'],
                seq=row['seq'],
                table=row['table'],
                from_col=row['from'],
                to_col=row['to'],
                on_update=row['on_update'],
                on_delete=row['on_delete'],
                match=row['match']
            ))

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        row_count = cursor.fetchone()[0]

        return TableInfo(
            name=table_name,
            columns=columns,
            foreign_keys=foreign_keys,
            row_count=row_count
        )


def get_all_tables() -> list[str]:
    """Get list of all tables in the target database."""
    db = get_db_manager()

    with db.get_target_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row['name'] for row in cursor.fetchall()]


def introspect_all_tables() -> list[TableInfo]:
    """Introspect all tables in the target database."""
    tables = get_all_tables()
    return [introspect_table(table) for table in tables]


def cache_table_metadata():
    """Cache table metadata in the system database."""
    db = get_db_manager()
    tables = introspect_all_tables()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        # Clear existing metadata
        cursor.execute("DELETE FROM table_metadata")

        # Insert new metadata
        for table in tables:
            columns_json = json.dumps([asdict(c) for c in table.columns])
            fk_json = json.dumps([asdict(fk) for fk in table.foreign_keys])

            cursor.execute(
                "INSERT INTO table_metadata (table_name, row_count, columns_json, foreign_keys_json) "
                "VALUES (?, ?, ?, ?)",
                (table.name, table.row_count, columns_json, fk_json)
            )

        conn.commit()


def get_cached_metadata() -> list[dict]:
    """Get cached table metadata from system database."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table_metadata ORDER BY table_name")
        rows = cursor.fetchall()

        return [
            {
                'table_name': row['table_name'],
                'row_count': row['row_count'],
                'columns': json.loads(row['columns_json']),
                'foreign_keys': json.loads(row['foreign_keys_json'])
            }
            for row in rows
        ]


def clear_metadata_cache():
    """Clear the metadata cache."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM table_metadata")
        cursor.execute("DELETE FROM column_semantics")
        conn.commit()
