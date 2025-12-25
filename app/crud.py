"""CRUD engine for target database tables."""
from datetime import datetime
from typing import Any, Optional

from app.database import get_db_manager
from app.introspection import introspect_table, ColumnInfo
from app.semantics import (
    get_table_semantics,
    is_auto_timestamp_column,
    is_auto_user_column,
    supports_soft_delete,
    get_soft_delete_column,
)


def get_input_type(column: ColumnInfo, semantic_type: Optional[str] = None) -> str:
    """Map SQLite column type to HTML input type."""
    col_type = column.type.upper()

    if semantic_type in ('created_at', 'updated_at', 'deleted_at'):
        return 'datetime-local'

    if 'INT' in col_type:
        return 'number'
    if 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
        return 'number'
    if 'BOOL' in col_type:
        return 'checkbox'
    if 'DATE' in col_type:
        return 'date'
    if 'TIME' in col_type:
        return 'datetime-local'
    if 'TEXT' in col_type and column.name.lower() in ('description', 'content', 'body', 'notes', 'bio'):
        return 'textarea'

    return 'text'


def should_show_on_create(column: ColumnInfo, semantic_type: Optional[str] = None) -> bool:
    """Determine if column should be shown on create form."""
    # Hide primary key auto-increment columns
    if column.pk and 'INT' in column.type.upper():
        return False

    # Hide auto-timestamp columns
    if semantic_type in ('created_at', 'updated_at'):
        return False

    return True


def should_show_on_edit(column: ColumnInfo, semantic_type: Optional[str] = None) -> bool:
    """Determine if column should be shown on edit form."""
    # Hide primary key columns
    if column.pk:
        return False

    # Hide created_at (shouldn't change on edit)
    if semantic_type == 'created_at':
        return False

    # Hide updated_at (auto-updated)
    if semantic_type == 'updated_at':
        return False

    return True


def get_form_fields(table_name: str, mode: str = 'create') -> list[dict]:
    """
    Get form field definitions for a table.

    Args:
        table_name: Name of the table
        mode: 'create' or 'edit'

    Returns:
        List of field definitions with name, type, required, etc.
    """
    table_info = introspect_table(table_name)
    semantics = get_table_semantics(table_name)

    fields = []
    for column in table_info.columns:
        semantic_type = semantics.get(column.name)

        if mode == 'create' and not should_show_on_create(column, semantic_type):
            continue
        if mode == 'edit' and not should_show_on_edit(column, semantic_type):
            continue

        fields.append({
            'name': column.name,
            'type': get_input_type(column, semantic_type),
            'required': column.notnull and column.default_value is None and not column.pk,
            'default': column.default_value,
            'semantic_type': semantic_type,
            'sql_type': column.type,
        })

    return fields


def list_rows(
    table_name: str,
    page: int = 1,
    page_size: int = 25,
    sort_column: Optional[str] = None,
    sort_order: str = 'asc',
    search: Optional[str] = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    """
    List rows from a table with pagination, sorting, and search.

    Returns:
        Tuple of (rows, total_count)
    """
    db = get_db_manager()
    table_info = introspect_table(table_name)

    # Build query
    columns = [c.name for c in table_info.columns]
    pk_column = next((c.name for c in table_info.columns if c.pk), columns[0])

    where_clauses = []
    params = []

    # Soft delete filter
    if not include_deleted:
        deleted_col = get_soft_delete_column(table_name)
        if deleted_col:
            where_clauses.append(f'"{deleted_col}" IS NULL')

    # Search filter
    if search:
        search_conditions = []
        for col in columns:
            search_conditions.append(f'CAST("{col}" AS TEXT) LIKE ?')
            params.append(f'%{search}%')
        if search_conditions:
            where_clauses.append(f'({" OR ".join(search_conditions)})')

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    # Sort
    if sort_column and sort_column in columns:
        order_sql = f'ORDER BY "{sort_column}" {sort_order.upper()}'
    else:
        order_sql = f'ORDER BY "{pk_column}" ASC'

    # Pagination
    offset = (page - 1) * page_size
    limit_sql = f'LIMIT {page_size} OFFSET {offset}'

    with db.get_target_connection() as conn:
        cursor = conn.cursor()

        # Get total count
        count_sql = f'SELECT COUNT(*) FROM "{table_name}" {where_sql}'
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        # Get rows
        select_sql = f'SELECT * FROM "{table_name}" {where_sql} {order_sql} {limit_sql}'
        cursor.execute(select_sql, params)

        rows = [dict(row) for row in cursor.fetchall()]

    return rows, total_count


def get_row(table_name: str, pk_value: Any) -> Optional[dict]:
    """Get a single row by primary key."""
    db = get_db_manager()
    table_info = introspect_table(table_name)

    pk_column = next((c.name for c in table_info.columns if c.pk), None)
    if not pk_column:
        pk_column = table_info.columns[0].name

    with db.get_target_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM "{table_name}" WHERE "{pk_column}" = ?', (pk_value,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_row(table_name: str, data: dict, current_user: Optional[str] = None) -> int:
    """
    Create a new row in the table.

    Returns:
        The ID of the created row
    """
    db = get_db_manager()
    semantics = get_table_semantics(table_name)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Auto-fill semantic columns
    for col, sem_type in semantics.items():
        if sem_type == 'created_at' and col not in data:
            data[col] = now
        elif sem_type == 'updated_at' and col not in data:
            data[col] = now
        elif sem_type == 'created_by' and col not in data and current_user:
            data[col] = current_user
        elif sem_type == 'updated_by' and col not in data and current_user:
            data[col] = current_user

    columns = list(data.keys())
    placeholders = ', '.join(['?' for _ in columns])
    column_list = ', '.join([f'"{c}"' for c in columns])
    values = list(data.values())

    with db.get_target_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f'INSERT INTO "{table_name}" ({column_list}) VALUES ({placeholders})',
            values
        )
        conn.commit()
        return cursor.lastrowid


def update_row(
    table_name: str,
    pk_value: Any,
    data: dict,
    current_user: Optional[str] = None
) -> bool:
    """
    Update an existing row.

    Returns:
        True if row was updated
    """
    db = get_db_manager()
    table_info = introspect_table(table_name)
    semantics = get_table_semantics(table_name)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    pk_column = next((c.name for c in table_info.columns if c.pk), table_info.columns[0].name)

    # Auto-update semantic columns
    for col, sem_type in semantics.items():
        if sem_type == 'updated_at':
            data[col] = now
        elif sem_type == 'updated_by' and current_user:
            data[col] = current_user

    set_clauses = ', '.join([f'"{k}" = ?' for k in data.keys()])
    values = list(data.values()) + [pk_value]

    with db.get_target_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f'UPDATE "{table_name}" SET {set_clauses} WHERE "{pk_column}" = ?',
            values
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_row(table_name: str, pk_value: Any, current_user: Optional[str] = None) -> bool:
    """
    Delete a row (soft delete if supported, hard delete otherwise).

    Returns:
        True if row was deleted
    """
    db = get_db_manager()
    table_info = introspect_table(table_name)

    pk_column = next((c.name for c in table_info.columns if c.pk), table_info.columns[0].name)

    # Check for soft delete
    deleted_col = get_soft_delete_column(table_name)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with db.get_target_connection() as conn:
        cursor = conn.cursor()

        if deleted_col:
            # Soft delete
            cursor.execute(
                f'UPDATE "{table_name}" SET "{deleted_col}" = ? WHERE "{pk_column}" = ?',
                (now, pk_value)
            )
        else:
            # Hard delete
            cursor.execute(
                f'DELETE FROM "{table_name}" WHERE "{pk_column}" = ?',
                (pk_value,)
            )

        conn.commit()
        return cursor.rowcount > 0


def get_pk_column(table_name: str) -> str:
    """Get the primary key column name for a table."""
    table_info = introspect_table(table_name)
    pk_column = next((c.name for c in table_info.columns if c.pk), None)
    return pk_column or table_info.columns[0].name
