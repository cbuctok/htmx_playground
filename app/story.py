"""Story Mode - Dependency Graph & Guided Record Creation.

This module implements Story Mode, which transforms the database
from "a pile of tables" into a guided data story by:
1. Building a directed dependency graph from foreign key relationships
2. Identifying root tables (heavily referenced) and leaf tables (depend on others)
3. Generating an ordered sequence of story steps
4. Providing guided data entry flow for users
5. Demo/Play mode for showcasing to customers
"""
import json
import random
import string
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Any

from app.database import get_db_manager
from app.introspection import get_all_tables, get_cached_metadata, introspect_table


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

        # Insert dependencies (use INSERT OR IGNORE to handle duplicate FK relationships)
        for from_table, to_table in graph['edges']:
            cursor.execute(
                "INSERT OR IGNORE INTO table_dependencies (from_table, to_table) VALUES (?, ?)",
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


# =============================================================================
# Demo/Play Mode - Sample Data Generation
# =============================================================================

# Sample data pools for generating realistic demo data
SAMPLE_DATA = {
    'first_names': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry', 'Iris', 'Jack',
                    'Kate', 'Leo', 'Mia', 'Noah', 'Olivia', 'Peter', 'Quinn', 'Rose', 'Sam', 'Tina'],
    'last_names': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson'],
    'companies': ['Acme Corp', 'TechVenture', 'GlobalSoft', 'DataFlow', 'CloudNine', 'InnovateTech', 'Synergy Inc'],
    'cities': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Seattle', 'Boston', 'Denver'],
    'countries': ['USA', 'Canada', 'UK', 'Germany', 'France', 'Japan', 'Australia'],
    'categories': ['Electronics', 'Books', 'Clothing', 'Home & Garden', 'Sports', 'Toys', 'Food', 'Health'],
    'products': ['Widget', 'Gadget', 'Device', 'Tool', 'Kit', 'Set', 'Pack', 'Bundle'],
    'adjectives': ['Premium', 'Standard', 'Basic', 'Pro', 'Ultra', 'Super', 'Mini', 'Mega', 'Classic', 'Modern'],
    'statuses': ['active', 'pending', 'completed', 'cancelled', 'draft', 'published', 'archived'],
    'colors': ['Red', 'Blue', 'Green', 'Yellow', 'Black', 'White', 'Silver', 'Gold'],
    'lorem': ['Lorem ipsum dolor sit amet', 'Consectetur adipiscing elit', 'Sed do eiusmod tempor',
              'Incididunt ut labore et dolore', 'Magna aliqua ut enim', 'Ad minim veniam quis nostrud'],
}


def _generate_sample_value(column_name: str, column_type: str, table_name: str) -> Any:
    """
    Generate a sample value based on column name and type.

    Uses heuristics to generate realistic-looking data.
    """
    col_lower = column_name.lower()
    col_type_upper = column_type.upper()

    # Handle specific column name patterns
    if col_lower in ('id', 'pk') or col_lower.endswith('_id'):
        return None  # Let autoincrement handle it or use FK lookup

    # Name fields
    if 'first' in col_lower and 'name' in col_lower:
        return random.choice(SAMPLE_DATA['first_names'])
    if 'last' in col_lower and 'name' in col_lower:
        return random.choice(SAMPLE_DATA['last_names'])
    if col_lower in ('name', 'full_name', 'fullname'):
        return f"{random.choice(SAMPLE_DATA['first_names'])} {random.choice(SAMPLE_DATA['last_names'])}"
    if col_lower in ('username', 'user_name', 'login'):
        return f"{random.choice(SAMPLE_DATA['first_names']).lower()}{random.randint(1, 999)}"

    # Email
    if 'email' in col_lower:
        name = random.choice(SAMPLE_DATA['first_names']).lower()
        domain = random.choice(['example.com', 'demo.com', 'test.org', 'sample.net'])
        return f"{name}{random.randint(1, 99)}@{domain}"

    # Phone
    if 'phone' in col_lower or 'tel' in col_lower:
        return f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"

    # Address fields
    if 'city' in col_lower:
        return random.choice(SAMPLE_DATA['cities'])
    if 'country' in col_lower:
        return random.choice(SAMPLE_DATA['countries'])
    if 'address' in col_lower or 'street' in col_lower:
        return f"{random.randint(100, 9999)} {random.choice(SAMPLE_DATA['last_names'])} St"
    if 'zip' in col_lower or 'postal' in col_lower:
        return f"{random.randint(10000, 99999)}"

    # Company/Organization
    if 'company' in col_lower or 'organization' in col_lower or 'org' in col_lower:
        return random.choice(SAMPLE_DATA['companies'])

    # Product/Item fields
    if col_lower in ('title', 'product_name', 'item_name') or (table_name and 'product' in table_name.lower()):
        adj = random.choice(SAMPLE_DATA['adjectives'])
        prod = random.choice(SAMPLE_DATA['products'])
        color = random.choice(SAMPLE_DATA['colors'])
        return f"{adj} {color} {prod}"

    # Category
    if 'category' in col_lower or 'type' in col_lower:
        return random.choice(SAMPLE_DATA['categories'])

    # Description/Content
    if 'description' in col_lower or 'content' in col_lower or 'body' in col_lower:
        return '. '.join(random.sample(SAMPLE_DATA['lorem'], min(3, len(SAMPLE_DATA['lorem']))))
    if 'notes' in col_lower or 'comment' in col_lower:
        return random.choice(SAMPLE_DATA['lorem'])

    # Status
    if 'status' in col_lower or 'state' in col_lower:
        return random.choice(SAMPLE_DATA['statuses'])

    # Boolean fields
    if col_lower.startswith('is_') or col_lower.startswith('has_') or 'active' in col_lower or 'enabled' in col_lower:
        return random.choice([0, 1])
    if 'BOOL' in col_type_upper:
        return random.choice([0, 1])

    # Price/Amount fields
    if 'price' in col_lower or 'amount' in col_lower or 'cost' in col_lower or 'total' in col_lower:
        return round(random.uniform(9.99, 999.99), 2)
    if 'quantity' in col_lower or 'qty' in col_lower or 'count' in col_lower:
        return random.randint(1, 100)

    # Date/Time fields
    if 'date' in col_lower or 'time' in col_lower or 'created' in col_lower or 'updated' in col_lower:
        if 'DATETIME' in col_type_upper or 'TIMESTAMP' in col_type_upper or 'time' in col_lower:
            days_ago = random.randint(0, 365)
            dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            days_ago = random.randint(0, 365)
            dt = datetime.now() - timedelta(days=days_ago)
            return dt.strftime('%Y-%m-%d')

    # Numeric types
    if 'INT' in col_type_upper:
        return random.randint(1, 1000)
    if 'REAL' in col_type_upper or 'FLOAT' in col_type_upper or 'DOUBLE' in col_type_upper:
        return round(random.uniform(1.0, 1000.0), 2)

    # Default: generate a text value
    return f"{table_name}_{column_name}_{random.randint(1, 1000)}"


def _get_random_fk_value(table_name: str, column_name: str) -> Optional[int]:
    """
    Get a random existing ID from a referenced table for FK columns.
    """
    db = get_db_manager()

    # Get FK info for this column
    table_info = introspect_table(table_name)
    fk_info = None
    for fk in table_info.foreign_keys:
        if fk.from_col == column_name:
            fk_info = fk
            break

    if not fk_info:
        return None

    # Get a random ID from the referenced table
    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT "{fk_info.to_col}" FROM "{fk_info.table}" ORDER BY RANDOM() LIMIT 1')
            row = cursor.fetchone()
            if row:
                return row[0]
    except Exception:
        pass

    return None


def generate_demo_row(table_name: str) -> dict:
    """
    Generate a single demo row for a table.

    Returns a dict of column -> value mappings.
    """
    table_info = introspect_table(table_name)
    row_data = {}

    # Build FK column lookup
    fk_columns = {fk.from_col: fk for fk in table_info.foreign_keys}

    for column in table_info.columns:
        # Skip primary key (autoincrement)
        if column.pk:
            continue

        # Handle foreign key columns
        if column.name in fk_columns:
            fk_value = _get_random_fk_value(table_name, column.name)
            if fk_value is not None:
                row_data[column.name] = fk_value
            continue

        # Generate sample value
        value = _generate_sample_value(column.name, column.type, table_name)
        if value is not None:
            row_data[column.name] = value

    return row_data


def insert_demo_row(table_name: str, row_data: Optional[dict] = None) -> Optional[int]:
    """
    Insert a demo row into a table.

    Args:
        table_name: Name of the table
        row_data: Optional pre-generated row data. If None, generates new data.

    Returns:
        The ID of the inserted row, or None if failed.
    """
    if row_data is None:
        row_data = generate_demo_row(table_name)

    if not row_data:
        return None

    db = get_db_manager()

    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()

            columns = list(row_data.keys())
            values = list(row_data.values())
            placeholders = ', '.join(['?' for _ in values])
            column_names = ', '.join([f'"{c}"' for c in columns])

            cursor.execute(
                f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})',
                values
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Error inserting demo row into {table_name}: {e}")
        return None


def play_story_step(step: StoryStep, num_records: int = 1) -> dict:
    """
    Execute a story step by inserting demo records.

    Args:
        step: The story step to play
        num_records: Number of records to insert

    Returns:
        Dict with 'success', 'inserted_count', 'inserted_ids', 'error' (if any)
    """
    if step.source_type != 'table':
        return {'success': False, 'inserted_count': 0, 'inserted_ids': [], 'error': 'Only table steps can be played'}

    inserted_ids = []
    errors = []

    for i in range(num_records):
        row_data = generate_demo_row(step.source_name)
        row_id = insert_demo_row(step.source_name, row_data)

        if row_id is not None:
            inserted_ids.append(row_id)
        else:
            errors.append(f"Failed to insert record {i + 1}")

    return {
        'success': len(inserted_ids) > 0,
        'inserted_count': len(inserted_ids),
        'inserted_ids': inserted_ids,
        'errors': errors if errors else None,
        'step_id': step.id,
        'table_name': step.source_name,
    }


def play_all_story_steps(records_per_step: int = 1) -> list[dict]:
    """
    Play through all enabled story steps, inserting demo data.

    Args:
        records_per_step: Number of records to insert per step

    Returns:
        List of results for each step
    """
    steps = get_story_steps(include_disabled=False)
    results = []

    for step in steps:
        result = play_story_step(step, records_per_step)
        results.append(result)

    return results


def get_demo_preview(table_name: str, num_samples: int = 3) -> list[dict]:
    """
    Generate preview data for a table without inserting.

    Useful for showing what demo data would look like.
    """
    return [generate_demo_row(table_name) for _ in range(num_samples)]


def clear_demo_data(table_name: str) -> int:
    """
    Clear all data from a table (for resetting demos).

    Returns the number of rows deleted.
    """
    db = get_db_manager()

    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            count = cursor.fetchone()[0]

            cursor.execute(f'DELETE FROM "{table_name}"')
            conn.commit()
            return count
    except Exception:
        return 0


def clear_all_demo_data() -> dict:
    """
    Clear all data from all tables in reverse dependency order.

    Returns dict with table names and deleted counts.
    """
    # Get tables in reverse order (leaves first, then roots)
    ordered_tables = list(reversed(topological_sort_tables()))
    results = {}

    for table_name in ordered_tables:
        count = clear_demo_data(table_name)
        results[table_name] = count

    return results
