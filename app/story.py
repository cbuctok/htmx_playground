"""Story Mode - Dependency Graph & Guided Record Creation.

This module implements Story Mode, which transforms the database
from "a pile of tables" into a guided data story by:
1. Building a directed dependency graph from foreign key relationships
2. Identifying root tables (heavily referenced) and leaf tables (depend on others)
3. Generating an ordered sequence of story steps
4. Providing guided data entry flow for users
"""
import json
from dataclasses import dataclass, asdict
from typing import Optional

from app.database import get_db_manager
from app.introspection import get_all_tables, get_cached_metadata


@dataclass
class TableDependency:
    """Represents a dependency relationship between tables."""
    from_table: str
    to_table: str
    from_column: str
    to_column: str


@dataclass
class StoryStep:
    """Represents a step in the story flow."""
    id: int
    source_type: str  # 'table' or 'view'
    source_name: str
    order_index: int
    title: str
    description: str
    min_records_required: int
    enabled: bool


def build_dependency_graph() -> dict:
    """
    Build a directed dependency graph from foreign key relationships.

    Returns a dict with:
    - nodes: set of all table names
    - edges: list of (from_table, to_table) tuples
    - outgoing: dict mapping table -> tables it references
    - incoming: dict mapping table -> tables that reference it
    - in_degree: dict mapping table -> number of tables that reference it
    - out_degree: dict mapping table -> number of tables it references
    """
    metadata = get_cached_metadata()

    nodes = set()
    edges = []
    outgoing = {}  # table -> tables it references (depends on)
    incoming = {}  # table -> tables that reference it (dependents)

    for table_info in metadata:
        table_name = table_info['table_name']
        nodes.add(table_name)
        outgoing.setdefault(table_name, [])
        incoming.setdefault(table_name, [])

        for fk in table_info.get('foreign_keys', []):
            referenced_table = fk['table']
            if referenced_table:
                edges.append((table_name, referenced_table))
                outgoing.setdefault(table_name, []).append(referenced_table)
                incoming.setdefault(referenced_table, []).append(table_name)
                # Ensure referenced table is in nodes
                nodes.add(referenced_table)

    # Calculate degrees
    in_degree = {t: len(incoming.get(t, [])) for t in nodes}
    out_degree = {t: len(outgoing.get(t, [])) for t in nodes}

    return {
        'nodes': nodes,
        'edges': edges,
        'outgoing': outgoing,
        'incoming': incoming,
        'in_degree': in_degree,
        'out_degree': out_degree,
    }


def topological_sort_tables() -> list[str]:
    """
    Perform topological sort on tables based on foreign key dependencies.

    Root tables (no foreign keys, heavily referenced) come first.
    Leaf tables (many foreign keys, depend on others) come last.

    Returns ordered list of table names from roots to leaves.
    """
    graph = build_dependency_graph()
    nodes = graph['nodes']
    outgoing = graph['outgoing']

    # Kahn's algorithm for topological sort
    in_degree = {t: 0 for t in nodes}
    for table in nodes:
        for dep in outgoing.get(table, []):
            if dep in in_degree:
                in_degree[dep] += 1

    # Actually, we want reverse order: tables with no FKs first
    # A table that references others should come AFTER those others
    # So we reverse the edge direction for sorting

    # Build reverse in-degree (how many tables does this table reference)
    ref_count = {t: len(outgoing.get(t, [])) for t in nodes}

    # Start with tables that don't reference any other tables
    queue = [t for t in nodes if ref_count[t] == 0]
    result = []
    visited = set()

    # Sort queue by how many tables reference this table (descending)
    # This puts heavily-referenced root tables first
    queue.sort(key=lambda t: -graph['in_degree'].get(t, 0))

    while queue:
        table = queue.pop(0)
        if table in visited:
            continue
        visited.add(table)
        result.append(table)

        # Find tables that depend on this one
        for dependent in graph['incoming'].get(table, []):
            if dependent not in visited:
                # Check if all dependencies of this table are visited
                deps = outgoing.get(dependent, [])
                if all(d in visited for d in deps):
                    queue.append(dependent)

        # Re-sort queue by in_degree (heavily referenced first)
        queue.sort(key=lambda t: -graph['in_degree'].get(t, 0))

    # Add any remaining tables (circular dependencies or isolated)
    for table in nodes:
        if table not in visited:
            result.append(table)

    return result


def generate_default_story_steps() -> list[dict]:
    """
    Generate default story steps based on dependency graph.

    Returns list of step dicts ready for database insertion.
    """
    ordered_tables = topological_sort_tables()

    steps = []
    for i, table_name in enumerate(ordered_tables):
        # Generate a human-readable title
        title = table_name.replace('_', ' ').title()

        # Generate a description based on position
        graph = build_dependency_graph()
        out_deg = graph['out_degree'].get(table_name, 0)
        in_deg = graph['in_degree'].get(table_name, 0)

        if out_deg == 0 and in_deg > 0:
            description = f"This is a root table. {in_deg} other table(s) depend on it."
        elif out_deg > 0 and in_deg == 0:
            description = f"This table references {out_deg} other table(s)."
        elif out_deg > 0 and in_deg > 0:
            description = f"This table references {out_deg} table(s) and is referenced by {in_deg} table(s)."
        else:
            description = "This is a standalone table with no foreign key relationships."

        steps.append({
            'source_type': 'table',
            'source_name': table_name,
            'order_index': i,
            'title': title,
            'description': description,
            'min_records_required': 1,
            'enabled': True,
        })

    return steps


def cache_dependency_graph():
    """
    Build and persist the dependency graph in the system database.
    """
    db = get_db_manager()
    graph = build_dependency_graph()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        # Clear existing dependencies
        cursor.execute("DELETE FROM table_dependencies")

        # Insert dependencies
        for from_table, to_table in graph['edges']:
            cursor.execute(
                "INSERT INTO table_dependencies (from_table, to_table) VALUES (?, ?)",
                (from_table, to_table)
            )

        conn.commit()


def get_cached_dependencies() -> list[dict]:
    """Get cached table dependencies from system database."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table_dependencies")
        return [dict(row) for row in cursor.fetchall()]


def initialize_story_steps():
    """
    Initialize story steps if none exist.

    Called on startup to ensure story steps are populated.
    """
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM story_steps")
        count = cursor.fetchone()[0]

        if count == 0:
            regenerate_story_steps()


def regenerate_story_steps():
    """
    Regenerate story steps from current dependency graph.

    Clears existing steps and creates new ones based on FK relationships.
    """
    db = get_db_manager()
    steps = generate_default_story_steps()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        # Clear existing steps
        cursor.execute("DELETE FROM story_steps")

        # Insert new steps
        for step in steps:
            cursor.execute(
                """INSERT INTO story_steps
                   (source_type, source_name, order_index, title, description, min_records_required, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (step['source_type'], step['source_name'], step['order_index'],
                 step['title'], step['description'], step['min_records_required'],
                 step['enabled'])
            )

        conn.commit()


def get_story_steps(include_disabled: bool = False) -> list[StoryStep]:
    """
    Get all story steps ordered by order_index.

    Args:
        include_disabled: If True, includes disabled steps

    Returns:
        List of StoryStep objects
    """
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        if include_disabled:
            cursor.execute("SELECT * FROM story_steps ORDER BY order_index")
        else:
            cursor.execute("SELECT * FROM story_steps WHERE enabled = 1 ORDER BY order_index")

        return [
            StoryStep(
                id=row['id'],
                source_type=row['source_type'],
                source_name=row['source_name'],
                order_index=row['order_index'],
                title=row['title'],
                description=row['description'],
                min_records_required=row['min_records_required'],
                enabled=bool(row['enabled'])
            )
            for row in cursor.fetchall()
        ]


def get_story_step(step_id: int) -> Optional[StoryStep]:
    """Get a single story step by ID."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM story_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()

        if row:
            return StoryStep(
                id=row['id'],
                source_type=row['source_type'],
                source_name=row['source_name'],
                order_index=row['order_index'],
                title=row['title'],
                description=row['description'],
                min_records_required=row['min_records_required'],
                enabled=bool(row['enabled'])
            )
        return None


def update_story_step(
    step_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    min_records_required: Optional[int] = None,
    enabled: Optional[bool] = None,
    order_index: Optional[int] = None,
):
    """Update a story step's properties."""
    db = get_db_manager()

    updates = []
    values = []

    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if description is not None:
        updates.append("description = ?")
        values.append(description)
    if min_records_required is not None:
        updates.append("min_records_required = ?")
        values.append(min_records_required)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(1 if enabled else 0)
    if order_index is not None:
        updates.append("order_index = ?")
        values.append(order_index)

    if not updates:
        return

    values.append(step_id)

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE story_steps SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()


def reorder_story_steps(step_ids: list[int]):
    """
    Reorder story steps based on provided ID list.

    Args:
        step_ids: List of step IDs in desired order
    """
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()

        for i, step_id in enumerate(step_ids):
            cursor.execute(
                "UPDATE story_steps SET order_index = ? WHERE id = ?",
                (i, step_id)
            )

        conn.commit()


def is_story_mode_enabled() -> bool:
    """Check if Story Mode is enabled in app config."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_config WHERE key = 'story_mode_enabled'")
        row = cursor.fetchone()

        if row:
            return row['value'].lower() == 'true'
        return False


def set_story_mode_enabled(enabled: bool):
    """Enable or disable Story Mode."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES ('story_mode_enabled', ?)",
            ('true' if enabled else 'false',)
        )
        conn.commit()


def get_table_row_count(table_name: str) -> int:
    """Get current row count for a table."""
    db = get_db_manager()

    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
            return cursor.fetchone()[0]
    except Exception:
        return 0


def get_step_progress(step: StoryStep) -> dict:
    """
    Get progress info for a story step.

    Returns:
        Dict with current_count, required, is_complete, percentage
    """
    if step.source_type == 'table':
        current = get_table_row_count(step.source_name)
    else:
        current = 0  # Views don't have row counts in this context

    required = step.min_records_required
    is_complete = current >= required
    percentage = min(100, int((current / required) * 100)) if required > 0 else 100

    return {
        'current_count': current,
        'required': required,
        'is_complete': is_complete,
        'percentage': percentage,
    }


def get_story_progress() -> dict:
    """
    Get overall story progress.

    Returns:
        Dict with steps info and overall progress
    """
    steps = get_story_steps(include_disabled=False)

    step_progress = []
    completed_count = 0

    for step in steps:
        progress = get_step_progress(step)
        step_info = {
            'step': step,
            'progress': progress,
        }
        step_progress.append(step_info)

        if progress['is_complete']:
            completed_count += 1

    total_steps = len(steps)
    overall_percentage = int((completed_count / total_steps) * 100) if total_steps > 0 else 100

    return {
        'steps': step_progress,
        'total_steps': total_steps,
        'completed_steps': completed_count,
        'overall_percentage': overall_percentage,
        'is_complete': completed_count == total_steps,
    }


def get_current_story_step() -> Optional[dict]:
    """
    Get the current step the user should be working on.

    Returns the first incomplete step, or None if all complete.
    """
    progress = get_story_progress()

    for step_info in progress['steps']:
        if not step_info['progress']['is_complete']:
            return step_info

    return None


def get_table_dependencies_display(table_name: str) -> dict:
    """
    Get dependency info for a table for display purposes.

    Returns:
        Dict with 'depends_on' and 'depended_by' lists
    """
    graph = build_dependency_graph()

    return {
        'depends_on': graph['outgoing'].get(table_name, []),
        'depended_by': graph['incoming'].get(table_name, []),
    }


def reset_story():
    """
    Reset the story by regenerating steps from current schema.

    Called when schema changes or admin wants to reset.
    """
    cache_dependency_graph()
    regenerate_story_steps()
