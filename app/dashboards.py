"""Dashboard management."""
import json
from typing import Optional
from dataclasses import dataclass

from app.database import get_db_manager
from app.introspection import get_all_tables, introspect_table


@dataclass
class Dashboard:
    """Dashboard configuration."""
    id: int
    name: str
    config: dict


def get_default_dashboard_config() -> dict:
    """Generate default dashboard configuration from target DB tables."""
    tables = get_all_tables()

    table_widgets = []
    for table_name in tables:
        table_info = introspect_table(table_name)
        table_widgets.append({
            'type': 'table_summary',
            'table': table_name,
            'row_count': table_info.row_count,
            'column_count': len(table_info.columns),
        })

    return {
        'layout': 'grid',
        'widgets': table_widgets,
    }


def get_all_dashboards() -> list[Dashboard]:
    """Get all saved dashboards."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, config_json FROM dashboards ORDER BY name")
        return [
            Dashboard(
                id=row['id'],
                name=row['name'],
                config=json.loads(row['config_json'])
            )
            for row in cursor.fetchall()
        ]


def get_dashboard(dashboard_id: int) -> Optional[Dashboard]:
    """Get a specific dashboard."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json FROM dashboards WHERE id = ?",
            (dashboard_id,)
        )
        row = cursor.fetchone()

        if row:
            return Dashboard(
                id=row['id'],
                name=row['name'],
                config=json.loads(row['config_json'])
            )

    return None


def create_dashboard(name: str, config: Optional[dict] = None) -> int:
    """Create a new dashboard."""
    db = get_db_manager()

    if config is None:
        config = get_default_dashboard_config()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dashboards (name, config_json) VALUES (?, ?)",
            (name, json.dumps(config))
        )
        conn.commit()
        return cursor.lastrowid


def update_dashboard(dashboard_id: int, name: Optional[str] = None, config: Optional[dict] = None):
    """Update a dashboard."""
    db = get_db_manager()

    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if config is not None:
        updates.append("config_json = ?")
        params.append(json.dumps(config))

    if not updates:
        return

    params.append(dashboard_id)

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE dashboards SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()


def delete_dashboard(dashboard_id: int):
    """Delete a dashboard."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
        conn.commit()


def reset_dashboards():
    """Reset all dashboards (clear and recreate default)."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dashboards")
        conn.commit()

    # Create default dashboard
    create_dashboard("Default Dashboard", get_default_dashboard_config())


def get_saved_views() -> list[dict]:
    """Get all saved views."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, sql, source_table FROM views ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]


def create_view(name: str, sql: str, source_table: Optional[str] = None) -> int:
    """Create a new saved view."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO views (name, sql, source_table) VALUES (?, ?, ?)",
            (name, sql, source_table)
        )
        conn.commit()
        return cursor.lastrowid


def delete_view(view_id: int):
    """Delete a saved view."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM views WHERE id = ?", (view_id,))
        conn.commit()


def reset_views():
    """Reset all saved views."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM views")
        conn.commit()
