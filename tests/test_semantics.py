"""Tests for the semantics module."""
import pytest

from app.semantics import (
    SEMANTIC_PATTERNS,
    normalize_column_name,
    detect_semantic_type,
    analyze_table_semantics,
    cache_column_semantics,
    get_table_semantics,
    get_all_semantics,
    is_auto_timestamp_column,
    is_auto_user_column,
    supports_soft_delete,
    get_soft_delete_column,
)


class TestNormalizeColumnName:
    """Tests for normalize_column_name function."""

    def test_lowercase_conversion(self):
        """Should convert to lowercase."""
        assert normalize_column_name("CreatedAt") == "createdat"

    def test_underscore_removal(self):
        """Should remove underscores."""
        assert normalize_column_name("created_at") == "createdat"

    def test_hyphen_removal(self):
        """Should remove hyphens."""
        assert normalize_column_name("created-at") == "createdat"

    def test_combined_normalization(self):
        """Should handle combined cases."""
        assert normalize_column_name("Created_At") == "createdat"
        assert normalize_column_name("UPDATED-AT") == "updatedat"


class TestDetectSemanticType:
    """Tests for detect_semantic_type function."""

    # created_at patterns
    @pytest.mark.parametrize("column_name", [
        "created_at", "created-at", "createdAt", "CREATED_AT",
        "created_on", "created-on", "createdon", "CREATEDON",
        "date_created", "date-created", "datecreated",
        "creation_date", "creation-date", "creationdate",
        "created",
    ])
    def test_created_at_detection(self, column_name):
        """Should detect created_at semantic type."""
        assert detect_semantic_type(column_name) == "created_at"

    # updated_at patterns
    @pytest.mark.parametrize("column_name", [
        "updated_at", "updated-at", "updatedAt", "UPDATED_AT",
        "updated_on", "updated-on", "updatedon",
        "modified_at", "modified-at", "modifiedat",
        "modified_on", "modified-on", "modifiedon",
        "date_updated", "date_modified",
        "last_modified", "last-modified", "lastmodified",
        "last_updated", "last-updated", "lastupdated",
    ])
    def test_updated_at_detection(self, column_name):
        """Should detect updated_at semantic type."""
        assert detect_semantic_type(column_name) == "updated_at"

    # deleted_at patterns
    @pytest.mark.parametrize("column_name", [
        "deleted_at", "deleted-at", "deletedAt", "DELETED_AT",
        "deleted_on", "deleted-on", "deletedon",
        "date_deleted", "date-deleted", "datedeleted",
        "soft_deleted", "soft-deleted", "softdeleted",
    ])
    def test_deleted_at_detection(self, column_name):
        """Should detect deleted_at semantic type."""
        assert detect_semantic_type(column_name) == "deleted_at"

    # created_by patterns
    @pytest.mark.parametrize("column_name", [
        "created_by", "created-by", "createdBy", "CREATED_BY",
        "createdby", "author", "AUTHOR", "creator", "owner",
    ])
    def test_created_by_detection(self, column_name):
        """Should detect created_by semantic type."""
        assert detect_semantic_type(column_name) == "created_by"

    # updated_by patterns
    @pytest.mark.parametrize("column_name", [
        "updated_by", "updated-by", "updatedBy", "UPDATED_BY",
        "updatedby", "modified_by", "modified-by", "modifiedby",
        "last_modified_by", "last-modified-by", "editor",
    ])
    def test_updated_by_detection(self, column_name):
        """Should detect updated_by semantic type."""
        assert detect_semantic_type(column_name) == "updated_by"

    # status patterns
    @pytest.mark.parametrize("column_name", [
        "status", "STATUS", "state", "STATE",
        "is_active", "is-active", "isactive",
        "active", "ACTIVE", "enabled", "is_enabled",
    ])
    def test_status_detection(self, column_name):
        """Should detect status semantic type."""
        assert detect_semantic_type(column_name) == "status"

    # Non-semantic columns
    @pytest.mark.parametrize("column_name", [
        "id", "name", "email", "description", "price",
        "username", "password", "title", "content",
        "some_random_column", "xyz_abc",
    ])
    def test_no_semantic_detection(self, column_name):
        """Should return None for non-semantic columns."""
        assert detect_semantic_type(column_name) is None


class TestAnalyzeTableSemantics:
    """Tests for analyze_table_semantics function."""

    def test_analyze_products_table(self, sample_target_db):
        """Should detect semantics in products table."""
        semantics = analyze_table_semantics("products")
        assert semantics.get("created_at") == "created_at"
        assert semantics.get("updated_at") == "updated_at"
        assert semantics.get("status") == "status"

    def test_analyze_tasks_table(self, sample_target_db):
        """Should detect semantics in tasks table with soft delete."""
        semantics = analyze_table_semantics("tasks")
        assert semantics.get("created_at") == "created_at"
        assert semantics.get("updated_at") == "updated_at"
        assert semantics.get("deleted_at") == "deleted_at"
        assert semantics.get("created_by") == "created_by"

    def test_analyze_employees_table(self, sample_target_db):
        """Should detect author/editor semantics."""
        semantics = analyze_table_semantics("employees")
        assert semantics.get("author") == "created_by"
        assert semantics.get("editor") == "updated_by"
        assert semantics.get("created_at") == "created_at"
        assert semantics.get("modified_at") == "updated_at"


class TestCacheColumnSemantics:
    """Tests for cache_column_semantics function."""

    def test_caches_semantics(self, initialized_system_db, sample_target_db):
        """Should cache semantics in system database."""
        cache_column_semantics()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM column_semantics")
            count = cursor.fetchone()[0]
            assert count > 0

    def test_clears_existing_cache(self, initialized_system_db, sample_target_db):
        """Should clear existing cache before caching."""
        # Cache twice
        cache_column_semantics()
        cache_column_semantics()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM column_semantics")
            count = cursor.fetchone()[0]
            # Should not have duplicates
            assert count < 20  # Reasonable upper bound


class TestGetTableSemantics:
    """Tests for get_table_semantics function."""

    def test_returns_cached_semantics(self, full_test_setup):
        """Should return cached semantics for a table."""
        semantics = get_table_semantics("products")
        assert "created_at" in semantics
        assert "updated_at" in semantics

    def test_returns_empty_for_unknown_table(self, full_test_setup):
        """Should return empty dict for unknown table."""
        semantics = get_table_semantics("nonexistent_table")
        assert semantics == {}


class TestGetAllSemantics:
    """Tests for get_all_semantics function."""

    def test_returns_all_semantics(self, full_test_setup):
        """Should return semantics for all tables."""
        all_semantics = get_all_semantics()
        assert "products" in all_semantics
        assert "tasks" in all_semantics


class TestIsAutoTimestampColumn:
    """Tests for is_auto_timestamp_column function."""

    def test_created_at_is_auto_timestamp(self):
        """created_at should be auto-timestamp."""
        assert is_auto_timestamp_column("created_at", {"created_at": "created_at"})

    def test_updated_at_is_auto_timestamp(self):
        """updated_at should be auto-timestamp."""
        assert is_auto_timestamp_column("updated_at", {"updated_at": "updated_at"})

    def test_deleted_at_is_not_auto_timestamp(self):
        """deleted_at should not be auto-timestamp."""
        assert not is_auto_timestamp_column("deleted_at", {"deleted_at": "deleted_at"})

    def test_regular_column_is_not_auto_timestamp(self):
        """Regular columns should not be auto-timestamp."""
        assert not is_auto_timestamp_column("name", {"name": None})


class TestIsAutoUserColumn:
    """Tests for is_auto_user_column function."""

    def test_created_by_is_auto_user(self):
        """created_by should be auto-user."""
        assert is_auto_user_column("created_by", {"created_by": "created_by"})

    def test_updated_by_is_auto_user(self):
        """updated_by should be auto-user."""
        assert is_auto_user_column("updated_by", {"updated_by": "updated_by"})

    def test_author_is_auto_user(self):
        """author should be auto-user."""
        assert is_auto_user_column("author", {"author": "created_by"})

    def test_regular_column_is_not_auto_user(self):
        """Regular columns should not be auto-user."""
        assert not is_auto_user_column("username", {"username": None})


class TestSupportsSoftDelete:
    """Tests for supports_soft_delete function."""

    def test_table_with_deleted_at(self, full_test_setup):
        """Table with deleted_at should support soft delete."""
        assert supports_soft_delete("tasks")

    def test_table_without_deleted_at(self, full_test_setup):
        """Table without deleted_at should not support soft delete."""
        assert not supports_soft_delete("products")


class TestGetSoftDeleteColumn:
    """Tests for get_soft_delete_column function."""

    def test_returns_column_name(self, full_test_setup):
        """Should return soft delete column name."""
        col = get_soft_delete_column("tasks")
        assert col == "deleted_at"

    def test_returns_none_for_no_soft_delete(self, full_test_setup):
        """Should return None for tables without soft delete."""
        col = get_soft_delete_column("products")
        assert col is None


class TestSemanticPatterns:
    """Tests for SEMANTIC_PATTERNS constant."""

    def test_patterns_exist(self):
        """All expected semantic types should exist."""
        assert "created_at" in SEMANTIC_PATTERNS
        assert "updated_at" in SEMANTIC_PATTERNS
        assert "deleted_at" in SEMANTIC_PATTERNS
        assert "created_by" in SEMANTIC_PATTERNS
        assert "updated_by" in SEMANTIC_PATTERNS
        assert "status" in SEMANTIC_PATTERNS

    def test_patterns_are_lists(self):
        """All patterns should be lists."""
        for semantic_type, patterns in SEMANTIC_PATTERNS.items():
            assert isinstance(patterns, list), f"{semantic_type} patterns is not a list"

    def test_patterns_are_valid_regex(self):
        """All patterns should be valid regex."""
        import re
        for semantic_type, patterns in SEMANTIC_PATTERNS.items():
            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error:
                    pytest.fail(f"Invalid regex in {semantic_type}: {pattern}")
