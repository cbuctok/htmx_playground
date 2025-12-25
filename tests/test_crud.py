"""Tests for the CRUD module."""
from datetime import datetime

import pytest

from app.crud import (
    get_input_type,
    should_show_on_create,
    should_show_on_edit,
    get_form_fields,
    list_rows,
    get_row,
    create_row,
    update_row,
    delete_row,
    get_pk_column,
)
from app.introspection import ColumnInfo


class TestGetInputType:
    """Tests for get_input_type function."""

    def test_integer_returns_number(self):
        """INTEGER columns should return 'number' input type."""
        col = ColumnInfo(0, "count", "INTEGER", False, None, False)
        assert get_input_type(col) == "number"

    def test_real_returns_number(self):
        """REAL columns should return 'number' input type."""
        col = ColumnInfo(0, "price", "REAL", False, None, False)
        assert get_input_type(col) == "number"

    def test_float_returns_number(self):
        """FLOAT columns should return 'number' input type."""
        col = ColumnInfo(0, "value", "FLOAT", False, None, False)
        assert get_input_type(col) == "number"

    def test_double_returns_number(self):
        """DOUBLE columns should return 'number' input type."""
        col = ColumnInfo(0, "amount", "DOUBLE", False, None, False)
        assert get_input_type(col) == "number"

    def test_bool_returns_checkbox(self):
        """BOOL columns should return 'checkbox' input type."""
        col = ColumnInfo(0, "active", "BOOL", False, None, False)
        assert get_input_type(col) == "checkbox"

    def test_date_returns_date(self):
        """DATE columns should return 'date' input type."""
        col = ColumnInfo(0, "birth_date", "DATE", False, None, False)
        assert get_input_type(col) == "date"

    def test_time_returns_datetime_local(self):
        """TIME columns should return 'datetime-local' input type."""
        col = ColumnInfo(0, "event_time", "TIME", False, None, False)
        assert get_input_type(col) == "datetime-local"

    def test_timestamp_semantic_returns_datetime_local(self):
        """Timestamp semantic columns should return 'datetime-local'."""
        col = ColumnInfo(0, "created_at", "TEXT", False, None, False)
        assert get_input_type(col, "created_at") == "datetime-local"
        assert get_input_type(col, "updated_at") == "datetime-local"
        assert get_input_type(col, "deleted_at") == "datetime-local"

    def test_description_returns_textarea(self):
        """Description TEXT columns should return 'textarea'."""
        col = ColumnInfo(0, "description", "TEXT", False, None, False)
        assert get_input_type(col) == "textarea"

    def test_content_returns_textarea(self):
        """Content TEXT columns should return 'textarea'."""
        col = ColumnInfo(0, "content", "TEXT", False, None, False)
        assert get_input_type(col) == "textarea"

    def test_notes_returns_textarea(self):
        """Notes TEXT columns should return 'textarea'."""
        col = ColumnInfo(0, "notes", "TEXT", False, None, False)
        assert get_input_type(col) == "textarea"

    def test_text_returns_text(self):
        """Default TEXT columns should return 'text'."""
        col = ColumnInfo(0, "name", "TEXT", False, None, False)
        assert get_input_type(col) == "text"


class TestShouldShowOnCreate:
    """Tests for should_show_on_create function."""

    def test_hides_auto_increment_pk(self):
        """Should hide auto-increment primary key columns."""
        col = ColumnInfo(0, "id", "INTEGER", True, None, True)
        assert should_show_on_create(col) is False

    def test_hides_created_at(self):
        """Should hide created_at columns."""
        col = ColumnInfo(0, "created_at", "TEXT", False, None, False)
        assert should_show_on_create(col, "created_at") is False

    def test_hides_updated_at(self):
        """Should hide updated_at columns."""
        col = ColumnInfo(0, "updated_at", "TEXT", False, None, False)
        assert should_show_on_create(col, "updated_at") is False

    def test_shows_regular_columns(self):
        """Should show regular columns."""
        col = ColumnInfo(0, "name", "TEXT", True, None, False)
        assert should_show_on_create(col) is True

    def test_shows_deleted_at(self):
        """Should show deleted_at columns (optional)."""
        col = ColumnInfo(0, "deleted_at", "TEXT", False, None, False)
        assert should_show_on_create(col, "deleted_at") is True

    def test_shows_created_by(self):
        """Should show created_by columns (may be auto-filled)."""
        col = ColumnInfo(0, "created_by", "TEXT", False, None, False)
        assert should_show_on_create(col, "created_by") is True


class TestShouldShowOnEdit:
    """Tests for should_show_on_edit function."""

    def test_hides_primary_key(self):
        """Should hide primary key columns."""
        col = ColumnInfo(0, "id", "INTEGER", True, None, True)
        assert should_show_on_edit(col) is False

    def test_hides_created_at(self):
        """Should hide created_at columns."""
        col = ColumnInfo(0, "created_at", "TEXT", False, None, False)
        assert should_show_on_edit(col, "created_at") is False

    def test_hides_updated_at(self):
        """Should hide updated_at columns."""
        col = ColumnInfo(0, "updated_at", "TEXT", False, None, False)
        assert should_show_on_edit(col, "updated_at") is False

    def test_shows_regular_columns(self):
        """Should show regular columns."""
        col = ColumnInfo(0, "name", "TEXT", True, None, False)
        assert should_show_on_edit(col) is True


class TestGetFormFields:
    """Tests for get_form_fields function."""

    def test_returns_list_of_fields(self, full_test_setup):
        """Should return list of field definitions."""
        fields = get_form_fields("products", "create")
        assert isinstance(fields, list)
        assert len(fields) > 0

    def test_field_structure(self, full_test_setup):
        """Fields should have correct structure."""
        fields = get_form_fields("products", "create")

        for field in fields:
            assert "name" in field
            assert "type" in field
            assert "required" in field
            assert "default" in field
            assert "semantic_type" in field
            assert "sql_type" in field

    def test_excludes_id_on_create(self, full_test_setup):
        """Should exclude id column on create."""
        fields = get_form_fields("products", "create")
        field_names = [f['name'] for f in fields]
        assert "id" not in field_names

    def test_excludes_timestamps_on_create(self, full_test_setup):
        """Should exclude timestamp columns on create."""
        fields = get_form_fields("products", "create")
        field_names = [f['name'] for f in fields]
        assert "created_at" not in field_names
        assert "updated_at" not in field_names

    def test_excludes_id_on_edit(self, full_test_setup):
        """Should exclude id column on edit."""
        fields = get_form_fields("products", "edit")
        field_names = [f['name'] for f in fields]
        assert "id" not in field_names


class TestListRows:
    """Tests for list_rows function."""

    def test_returns_rows_and_count(self, full_test_setup):
        """Should return tuple of rows and count."""
        rows, count = list_rows("products")

        assert isinstance(rows, list)
        assert isinstance(count, int)
        assert count >= 1

    def test_pagination(self, full_test_setup):
        """Should support pagination."""
        # Add more rows
        db = full_test_setup
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            for i in range(10):
                cursor.execute(
                    "INSERT INTO products (name, price) VALUES (?, ?)",
                    (f"Product {i}", 10.0 + i)
                )
            conn.commit()

        rows, count = list_rows("products", page=1, page_size=5)
        assert len(rows) == 5
        assert count >= 11

        rows2, _ = list_rows("products", page=2, page_size=5)
        assert len(rows2) == 5

    def test_search(self, full_test_setup):
        """Should support search."""
        rows, count = list_rows("products", search="Test")

        assert count >= 1
        for row in rows:
            assert "Test" in row.get('name', '') or "test" in str(row.values()).lower()

    def test_sorting(self, full_test_setup):
        """Should support sorting."""
        db = full_test_setup
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", ("AAA", 100))
            cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", ("ZZZ", 1))
            conn.commit()

        rows, _ = list_rows("products", sort_column="name", sort_order="asc")
        names = [r['name'] for r in rows]
        assert names == sorted(names)

        rows_desc, _ = list_rows("products", sort_column="name", sort_order="desc")
        names_desc = [r['name'] for r in rows_desc]
        assert names_desc == sorted(names_desc, reverse=True)

    def test_excludes_soft_deleted(self, full_test_setup):
        """Should exclude soft-deleted rows by default."""
        db = full_test_setup
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (title, deleted_at) VALUES (?, ?)",
                ("Deleted Task", "2024-01-01 00:00:00")
            )
            conn.commit()

        rows, count = list_rows("tasks")
        titles = [r['title'] for r in rows]
        assert "Deleted Task" not in titles

    def test_includes_soft_deleted_when_requested(self, full_test_setup):
        """Should include soft-deleted rows when requested."""
        db = full_test_setup
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (title, deleted_at) VALUES (?, ?)",
                ("Deleted Task 2", "2024-01-01 00:00:00")
            )
            conn.commit()

        rows, count = list_rows("tasks", include_deleted=True)
        titles = [r['title'] for r in rows]
        assert "Deleted Task 2" in titles


class TestGetRow:
    """Tests for get_row function."""

    def test_returns_row_by_pk(self, full_test_setup):
        """Should return row by primary key."""
        row = get_row("products", 1)

        assert row is not None
        assert row['id'] == 1

    def test_returns_none_for_missing_row(self, full_test_setup):
        """Should return None for missing row."""
        row = get_row("products", 99999)
        assert row is None

    def test_returns_dict(self, full_test_setup):
        """Should return dict."""
        row = get_row("products", 1)
        assert isinstance(row, dict)


class TestCreateRow:
    """Tests for create_row function."""

    def test_creates_row(self, full_test_setup):
        """Should create a new row."""
        row_id = create_row("products", {"name": "New Product", "price": 49.99})

        assert row_id is not None
        assert row_id > 0

        row = get_row("products", row_id)
        assert row['name'] == "New Product"
        assert row['price'] == 49.99

    def test_auto_fills_created_at(self, full_test_setup):
        """Should auto-fill created_at."""
        row_id = create_row("products", {"name": "Timestamp Test", "price": 10.0})

        row = get_row("products", row_id)
        assert row['created_at'] is not None
        assert len(row['created_at']) > 0

    def test_auto_fills_updated_at(self, full_test_setup):
        """Should auto-fill updated_at."""
        row_id = create_row("products", {"name": "Timestamp Test 2", "price": 10.0})

        row = get_row("products", row_id)
        assert row['updated_at'] is not None

    def test_auto_fills_created_by(self, full_test_setup):
        """Should auto-fill created_by."""
        row_id = create_row("tasks", {"title": "User Test"}, current_user="testuser")

        row = get_row("tasks", row_id)
        assert row['created_by'] == "testuser"

    def test_returns_last_row_id(self, full_test_setup):
        """Should return the last inserted row ID."""
        row_id = create_row("products", {"name": "ID Test", "price": 5.0})

        # Verify it's the actual ID
        row = get_row("products", row_id)
        assert row is not None


class TestUpdateRow:
    """Tests for update_row function."""

    def test_updates_row(self, full_test_setup):
        """Should update an existing row."""
        result = update_row("products", 1, {"name": "Updated Name"})

        assert result is True

        row = get_row("products", 1)
        assert row['name'] == "Updated Name"

    def test_auto_updates_updated_at(self, full_test_setup):
        """Should auto-update updated_at."""
        original = get_row("products", 1)
        original_updated_at = original['updated_at']

        update_row("products", 1, {"name": "Update Timestamp Test"})

        updated = get_row("products", 1)
        assert updated['updated_at'] != original_updated_at

    def test_auto_updates_updated_by(self, full_test_setup):
        """Should auto-update updated_by."""
        row_id = create_row("tasks", {"title": "Update By Test"})

        update_row("tasks", row_id, {"title": "Updated"}, current_user="editor")

        # Note: tasks doesn't have updated_by column, so this tests with employees table
        emp_id = create_row("employees", {"name": "Test"})
        update_row("employees", emp_id, {"name": "Updated"}, current_user="editor")

        emp = get_row("employees", emp_id)
        assert emp['editor'] == "editor"

    def test_returns_false_for_missing_row(self, full_test_setup):
        """Should return False for missing row."""
        result = update_row("products", 99999, {"name": "Nonexistent"})
        assert result is False


class TestDeleteRow:
    """Tests for delete_row function."""

    def test_hard_deletes_row(self, full_test_setup):
        """Should hard delete row without soft delete support."""
        row_id = create_row("products", {"name": "To Delete", "price": 1.0})

        result = delete_row("products", row_id)

        assert result is True

        row = get_row("products", row_id)
        assert row is None

    def test_soft_deletes_row(self, full_test_setup):
        """Should soft delete row with soft delete support."""
        row_id = create_row("tasks", {"title": "To Soft Delete"})

        result = delete_row("tasks", row_id)

        assert result is True

        # Row should still exist
        row = get_row("tasks", row_id)
        assert row is not None
        assert row['deleted_at'] is not None

    def test_returns_false_for_missing_row(self, full_test_setup):
        """Should return False for missing row."""
        result = delete_row("products", 99999)
        assert result is False


class TestGetPkColumn:
    """Tests for get_pk_column function."""

    def test_returns_primary_key(self, full_test_setup):
        """Should return primary key column name."""
        pk = get_pk_column("products")
        assert pk == "id"

    def test_returns_first_column_if_no_pk(self, full_test_setup):
        """Should return first column if no PK defined."""
        # Create table without explicit PK
        db = full_test_setup
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE no_pk (col1 TEXT, col2 TEXT)")
            conn.commit()

        pk = get_pk_column("no_pk")
        assert pk == "col1"
