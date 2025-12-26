"""Tests for Story Mode functionality."""
import pytest
import sqlite3
from pathlib import Path
from app.story import (
    build_dependency_graph,
    topological_sort_tables,
    generate_default_story_steps,
    get_story_steps,
    get_story_step,
    update_story_step,
    reorder_story_steps,
    regenerate_story_steps,
    is_story_mode_enabled,
    set_story_mode_enabled,
    get_step_progress,
    get_story_progress,
    get_current_story_step,
    get_table_dependencies_display,
    cache_dependency_graph,
    initialize_story_steps,
    reset_story,
    StoryStep,
    # Demo/Play mode functions
    generate_demo_row,
    insert_demo_row,
    play_story_step,
    play_all_story_steps,
    get_demo_preview,
    clear_demo_data,
    clear_all_demo_data,
    _generate_sample_value,
)
from app.database import get_db_manager, init_system_db
from app.introspection import cache_table_metadata


@pytest.fixture
def temp_databases(tmp_path):
    """Set up temporary system and target databases."""
    db = get_db_manager()

    # Create system database in temp location
    system_path = tmp_path / "system.db"
    db.system_db_path = system_path

    # Create target database with foreign key relationships
    target_path = tmp_path / "target.db"
    db.set_target_db(target_path, "target.db")

    # Initialize system database
    init_system_db()

    # Create target database with test tables
    conn = sqlite3.connect(str(target_path))
    cursor = conn.cursor()

    # Create tables with foreign key relationships
    # categories is a root table (no FKs, heavily referenced)
    cursor.execute('''
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')

    # users is another root table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT
        )
    ''')

    # products references categories
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            price REAL
        )
    ''')

    # orders references users
    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            order_date TEXT
        )
    ''')

    # order_items is a leaf table (references both products and orders)
    cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(id),
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER
        )
    ''')

    # Insert some test data
    cursor.execute("INSERT INTO categories (name) VALUES ('Electronics')")
    cursor.execute("INSERT INTO users (username) VALUES ('testuser')")

    conn.commit()
    conn.close()

    # Cache table metadata
    cache_table_metadata()

    yield db

    # Cleanup
    db.clear_target_db()


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph function."""

    def test_returns_graph_structure(self, temp_databases):
        """Test that graph contains expected keys."""
        graph = build_dependency_graph()

        assert 'nodes' in graph
        assert 'edges' in graph
        assert 'outgoing' in graph
        assert 'incoming' in graph
        assert 'in_degree' in graph
        assert 'out_degree' in graph

    def test_nodes_contain_all_tables(self, temp_databases):
        """Test that all tables are in the graph nodes."""
        graph = build_dependency_graph()

        assert 'categories' in graph['nodes']
        assert 'users' in graph['nodes']
        assert 'products' in graph['nodes']
        assert 'orders' in graph['nodes']
        assert 'order_items' in graph['nodes']

    def test_edges_contain_foreign_keys(self, temp_databases):
        """Test that edges represent FK relationships."""
        graph = build_dependency_graph()

        # products -> categories
        assert ('products', 'categories') in graph['edges']
        # orders -> users
        assert ('orders', 'users') in graph['edges']
        # order_items -> orders and products
        assert ('order_items', 'orders') in graph['edges']
        assert ('order_items', 'products') in graph['edges']

    def test_outgoing_maps_table_to_dependencies(self, temp_databases):
        """Test outgoing edges are correctly mapped."""
        graph = build_dependency_graph()

        # products depends on categories
        assert 'categories' in graph['outgoing'].get('products', [])
        # order_items depends on orders and products
        outgoing_order_items = graph['outgoing'].get('order_items', [])
        assert 'orders' in outgoing_order_items
        assert 'products' in outgoing_order_items

    def test_incoming_maps_table_to_dependents(self, temp_databases):
        """Test incoming edges are correctly mapped."""
        graph = build_dependency_graph()

        # categories is referenced by products
        assert 'products' in graph['incoming'].get('categories', [])
        # orders is referenced by order_items
        assert 'order_items' in graph['incoming'].get('orders', [])

    def test_in_degree_counts_references(self, temp_databases):
        """Test in_degree counts how many tables reference each table."""
        graph = build_dependency_graph()

        # categories is referenced by 1 table (products)
        assert graph['in_degree']['categories'] == 1
        # users is referenced by 1 table (orders)
        assert graph['in_degree']['users'] == 1
        # order_items is a leaf (referenced by 0)
        assert graph['in_degree']['order_items'] == 0

    def test_out_degree_counts_dependencies(self, temp_databases):
        """Test out_degree counts how many tables each table references."""
        graph = build_dependency_graph()

        # categories references nothing
        assert graph['out_degree']['categories'] == 0
        # products references 1 table (categories)
        assert graph['out_degree']['products'] == 1
        # order_items references 2 tables
        assert graph['out_degree']['order_items'] == 2


class TestTopologicalSortTables:
    """Tests for topological_sort_tables function."""

    def test_returns_all_tables(self, temp_databases):
        """Test that all tables are in the sorted list."""
        sorted_tables = topological_sort_tables()

        assert len(sorted_tables) == 5
        assert set(sorted_tables) == {'categories', 'users', 'products', 'orders', 'order_items'}

    def test_roots_come_before_dependents(self, temp_databases):
        """Test that root tables come before tables that depend on them."""
        sorted_tables = topological_sort_tables()

        # categories should come before products
        assert sorted_tables.index('categories') < sorted_tables.index('products')
        # users should come before orders
        assert sorted_tables.index('users') < sorted_tables.index('orders')
        # products and orders should come before order_items
        assert sorted_tables.index('products') < sorted_tables.index('order_items')
        assert sorted_tables.index('orders') < sorted_tables.index('order_items')


class TestGenerateDefaultStorySteps:
    """Tests for generate_default_story_steps function."""

    def test_generates_steps_for_all_tables(self, temp_databases):
        """Test that steps are generated for all tables."""
        steps = generate_default_story_steps()

        assert len(steps) == 5
        source_names = [s['source_name'] for s in steps]
        assert 'categories' in source_names
        assert 'users' in source_names
        assert 'products' in source_names
        assert 'orders' in source_names
        assert 'order_items' in source_names

    def test_steps_have_required_fields(self, temp_databases):
        """Test that each step has all required fields."""
        steps = generate_default_story_steps()

        for step in steps:
            assert 'source_type' in step
            assert 'source_name' in step
            assert 'order_index' in step
            assert 'title' in step
            assert 'description' in step
            assert 'min_records_required' in step
            assert 'enabled' in step

    def test_default_values(self, temp_databases):
        """Test default values for steps."""
        steps = generate_default_story_steps()

        for step in steps:
            assert step['source_type'] == 'table'
            assert step['min_records_required'] == 1
            assert step['enabled'] is True

    def test_steps_are_ordered(self, temp_databases):
        """Test that steps have sequential order_index."""
        steps = generate_default_story_steps()

        indices = [s['order_index'] for s in steps]
        assert indices == list(range(len(steps)))


class TestStoryModeEnabled:
    """Tests for story mode enable/disable functions."""

    def test_default_disabled(self, temp_databases):
        """Test that story mode is disabled by default."""
        assert is_story_mode_enabled() is False

    def test_enable_story_mode(self, temp_databases):
        """Test enabling story mode."""
        set_story_mode_enabled(True)
        assert is_story_mode_enabled() is True

    def test_disable_story_mode(self, temp_databases):
        """Test disabling story mode."""
        set_story_mode_enabled(True)
        set_story_mode_enabled(False)
        assert is_story_mode_enabled() is False


class TestStorySteps:
    """Tests for story step management functions."""

    def test_initialize_creates_steps(self, temp_databases):
        """Test that initialize_story_steps creates steps."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        assert len(steps) == 5

    def test_regenerate_clears_and_recreates(self, temp_databases):
        """Test that regenerate clears existing steps."""
        initialize_story_steps()
        initial_steps = get_story_steps(include_disabled=True)

        regenerate_story_steps()
        new_steps = get_story_steps(include_disabled=True)

        assert len(new_steps) == len(initial_steps)

    def test_get_story_step_by_id(self, temp_databases):
        """Test getting a specific step by ID."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        step = get_story_step(steps[0].id)
        assert step is not None
        assert step.id == steps[0].id

    def test_get_story_step_returns_none_for_invalid_id(self, temp_databases):
        """Test that invalid ID returns None."""
        initialize_story_steps()
        step = get_story_step(99999)
        assert step is None

    def test_update_story_step_title(self, temp_databases):
        """Test updating a step's title."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)
        step_id = steps[0].id

        update_story_step(step_id, title="New Title")
        updated = get_story_step(step_id)

        assert updated.title == "New Title"

    def test_update_story_step_description(self, temp_databases):
        """Test updating a step's description."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)
        step_id = steps[0].id

        update_story_step(step_id, description="New description")
        updated = get_story_step(step_id)

        assert updated.description == "New description"

    def test_update_story_step_enabled(self, temp_databases):
        """Test enabling/disabling a step."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)
        step_id = steps[0].id

        update_story_step(step_id, enabled=False)
        updated = get_story_step(step_id)

        assert updated.enabled is False

    def test_get_story_steps_excludes_disabled(self, temp_databases):
        """Test that disabled steps are excluded by default."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)
        step_id = steps[0].id

        update_story_step(step_id, enabled=False)

        enabled_steps = get_story_steps(include_disabled=False)
        disabled_ids = [s.id for s in enabled_steps]

        assert step_id not in disabled_ids

    def test_reorder_story_steps(self, temp_databases):
        """Test reordering steps."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)
        original_ids = [s.id for s in steps]

        # Reverse the order
        reversed_ids = list(reversed(original_ids))
        reorder_story_steps(reversed_ids)

        reordered_steps = get_story_steps(include_disabled=True)
        new_ids = [s.id for s in reordered_steps]

        assert new_ids == reversed_ids


class TestStoryProgress:
    """Tests for story progress tracking."""

    def test_get_step_progress(self, temp_databases):
        """Test getting progress for a single step."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        # Find categories step (which has 1 row from fixture)
        cat_step = next(s for s in steps if s.source_name == 'categories')
        progress = get_step_progress(cat_step)

        assert 'current_count' in progress
        assert 'required' in progress
        assert 'is_complete' in progress
        assert 'percentage' in progress

    def test_step_with_data_is_complete(self, temp_databases):
        """Test that step with sufficient data is marked complete."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        # categories has 1 row and requires 1
        cat_step = next(s for s in steps if s.source_name == 'categories')
        progress = get_step_progress(cat_step)

        assert progress['current_count'] >= 1
        assert progress['is_complete'] is True
        assert progress['percentage'] == 100

    def test_step_without_data_is_incomplete(self, temp_databases):
        """Test that step without data is marked incomplete."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        # order_items has 0 rows
        items_step = next(s for s in steps if s.source_name == 'order_items')
        progress = get_step_progress(items_step)

        assert progress['current_count'] == 0
        assert progress['is_complete'] is False
        assert progress['percentage'] == 0

    def test_get_story_progress(self, temp_databases):
        """Test getting overall story progress."""
        initialize_story_steps()
        progress = get_story_progress()

        assert 'steps' in progress
        assert 'total_steps' in progress
        assert 'completed_steps' in progress
        assert 'overall_percentage' in progress
        assert 'is_complete' in progress

    def test_get_current_story_step(self, temp_databases):
        """Test getting the current step to work on."""
        initialize_story_steps()
        current = get_current_story_step()

        # Should be the first incomplete step
        if current is not None:
            assert current['progress']['is_complete'] is False


class TestTableDependencies:
    """Tests for table dependency display."""

    def test_get_table_dependencies_display(self, temp_databases):
        """Test getting dependencies for display."""
        cache_dependency_graph()
        deps = get_table_dependencies_display('products')

        assert 'depends_on' in deps
        assert 'depended_by' in deps
        assert 'categories' in deps['depends_on']

    def test_root_table_has_no_dependencies(self, temp_databases):
        """Test that root tables have no outgoing dependencies."""
        cache_dependency_graph()
        deps = get_table_dependencies_display('categories')

        assert len(deps['depends_on']) == 0
        assert 'products' in deps['depended_by']


class TestResetStory:
    """Tests for story reset functionality."""

    def test_reset_story_regenerates_steps(self, temp_databases):
        """Test that reset_story regenerates everything."""
        initialize_story_steps()
        initial_steps = get_story_steps(include_disabled=True)

        # Modify a step
        update_story_step(initial_steps[0].id, title="Modified Title")

        # Reset
        reset_story()
        new_steps = get_story_steps(include_disabled=True)

        # Title should be regenerated (not "Modified Title")
        first_step = next(s for s in new_steps if s.source_name == initial_steps[0].source_name)
        assert first_step.title != "Modified Title"


# =============================================================================
# Demo/Play Mode Tests
# =============================================================================

class TestGenerateSampleValue:
    """Tests for sample value generation."""

    def test_generates_email(self, temp_databases):
        """Test email field generation."""
        value = _generate_sample_value('email', 'TEXT', 'users')
        assert '@' in value
        assert '.' in value

    def test_generates_phone(self, temp_databases):
        """Test phone field generation."""
        value = _generate_sample_value('phone', 'TEXT', 'users')
        assert value.startswith('+')

    def test_generates_name(self, temp_databases):
        """Test name field generation."""
        value = _generate_sample_value('name', 'TEXT', 'users')
        assert ' ' in value  # Full name has space

    def test_generates_price(self, temp_databases):
        """Test price field generation."""
        value = _generate_sample_value('price', 'REAL', 'orders')
        assert isinstance(value, float)
        assert value > 0

    def test_generates_integer(self, temp_databases):
        """Test integer field generation."""
        value = _generate_sample_value('count', 'INTEGER', 'items')
        assert isinstance(value, int)

    def test_generates_status(self, temp_databases):
        """Test status field generation."""
        value = _generate_sample_value('status', 'TEXT', 'orders')
        assert value in ['active', 'pending', 'completed', 'cancelled', 'draft', 'published', 'archived']


class TestGenerateDemoRow:
    """Tests for demo row generation."""

    def test_generates_row_for_table(self, temp_databases):
        """Test generating a demo row for a table."""
        row = generate_demo_row('categories')
        assert isinstance(row, dict)
        assert 'name' in row or 'description' in row

    def test_excludes_primary_key(self, temp_databases):
        """Test that PK is not included in generated row."""
        row = generate_demo_row('categories')
        assert 'id' not in row

    def test_handles_foreign_keys(self, temp_databases):
        """Test that FK columns reference existing data."""
        # First ensure parent table has data
        insert_demo_row('categories')

        # Now generate row for child table
        row = generate_demo_row('products')
        # category_id should be present if categories has data
        if 'category_id' in row:
            assert isinstance(row['category_id'], int)


class TestInsertDemoRow:
    """Tests for inserting demo rows."""

    def test_inserts_row(self, temp_databases):
        """Test inserting a demo row."""
        initial_count = get_db_manager()
        with initial_count.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM categories")
            before = cursor.fetchone()[0]

        row_id = insert_demo_row('categories')

        assert row_id is not None
        assert row_id > 0

        with initial_count.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM categories")
            after = cursor.fetchone()[0]

        assert after == before + 1

    def test_returns_none_on_failure(self, temp_databases):
        """Test that None is returned if insertion fails."""
        # Try to insert into non-existent table
        row_id = insert_demo_row('nonexistent_table', {'col': 'value'})
        assert row_id is None


class TestPlayStoryStep:
    """Tests for playing individual story steps."""

    def test_plays_step(self, temp_databases):
        """Test playing a story step."""
        initialize_story_steps()
        steps = get_story_steps(include_disabled=True)

        # Find a root table step
        cat_step = next(s for s in steps if s.source_name == 'categories')

        result = play_story_step(cat_step, num_records=2)

        assert result['success'] is True
        assert result['inserted_count'] == 2
        assert len(result['inserted_ids']) == 2

    def test_returns_error_for_view(self, temp_databases):
        """Test that playing a view step returns error."""
        # Create a fake view step
        fake_step = StoryStep(
            id=999,
            source_type='view',
            source_name='fake_view',
            order_index=0,
            title='Fake',
            description='',
            min_records_required=1,
            enabled=True
        )

        result = play_story_step(fake_step)

        assert result['success'] is False
        assert 'error' in result


class TestPlayAllStorySteps:
    """Tests for playing all story steps."""

    def test_plays_all_steps(self, temp_databases):
        """Test playing all story steps."""
        initialize_story_steps()

        results = play_all_story_steps(records_per_step=1)

        assert len(results) > 0
        # At least root tables should succeed
        successful = [r for r in results if r['success']]
        assert len(successful) > 0


class TestDemoPreview:
    """Tests for demo data preview."""

    def test_generates_preview(self, temp_databases):
        """Test generating preview data."""
        preview = get_demo_preview('categories', num_samples=3)

        assert len(preview) == 3
        for row in preview:
            assert isinstance(row, dict)


class TestClearDemoData:
    """Tests for clearing demo data."""

    def test_clears_table_data(self, temp_databases):
        """Test clearing data from a table."""
        # Insert some data
        insert_demo_row('categories')
        insert_demo_row('categories')

        count = clear_demo_data('categories')

        assert count >= 2

        # Verify table is empty
        db = get_db_manager()
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM categories")
            assert cursor.fetchone()[0] == 0

    def test_clears_all_tables(self, temp_databases):
        """Test clearing all table data."""
        # Insert data into multiple tables
        insert_demo_row('categories')
        insert_demo_row('users')

        results = clear_all_demo_data()

        assert 'categories' in results
        assert 'users' in results
