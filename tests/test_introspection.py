"""Tests for the introspection module."""
import json

import pytest

from app.introspection import (
    ColumnInfo,
    ForeignKeyInfo,
    TableInfo,
    introspect_table,
    get_all_tables,
    introspect_all_tables,
    cache_table_metadata,
    get_cached_metadata,
    clear_metadata_cache,
)


class TestColumnInfo:
    """Tests for ColumnInfo dataclass."""

    def test_column_info_creation(self):
        """Should create ColumnInfo with all fields."""
        col = ColumnInfo(
            cid=0,
            name="id",
            type="INTEGER",
            notnull=True,
            default_value=None,
            pk=True
        )
        assert col.cid == 0
        assert col.name == "id"
        assert col.type == "INTEGER"
        assert col.notnull is True
        assert col.default_value is None
        assert col.pk is True


class TestForeignKeyInfo:
    """Tests for ForeignKeyInfo dataclass."""

    def test_foreign_key_info_creation(self):
        """Should create ForeignKeyInfo with all fields."""
        fk = ForeignKeyInfo(
            id=0,
            seq=0,
            table="categories",
            from_col="category_id",
            to_col="id",
            on_update="NO ACTION",
            on_delete="NO ACTION",
            match="NONE"
        )
        assert fk.table == "categories"
        assert fk.from_col == "category_id"
        assert fk.to_col == "id"


class TestTableInfo:
    """Tests for TableInfo dataclass."""

    def test_table_info_creation(self):
        """Should create TableInfo with all fields."""
        col = ColumnInfo(0, "id", "INTEGER", True, None, True)
        fk = ForeignKeyInfo(0, 0, "other", "ref_id", "id", "NO ACTION", "NO ACTION", "NONE")
        table = TableInfo(
            name="test_table",
            columns=[col],
            foreign_keys=[fk],
            row_count=10
        )
        assert table.name == "test_table"
        assert len(table.columns) == 1
        assert len(table.foreign_keys) == 1
        assert table.row_count == 10


class TestIntrospectTable:
    """Tests for introspect_table function."""

    def test_introspects_products_table(self, sample_target_db):
        """Should introspect products table correctly."""
        info = introspect_table("products")

        assert info.name == "products"
        assert len(info.columns) > 0
        assert info.row_count >= 0

        # Check for expected columns
        column_names = [c.name for c in info.columns]
        assert "id" in column_names
        assert "name" in column_names
        assert "price" in column_names
        assert "category_id" in column_names

    def test_detects_primary_key(self, sample_target_db):
        """Should detect primary key column."""
        info = introspect_table("products")

        pk_columns = [c for c in info.columns if c.pk]
        assert len(pk_columns) == 1
        assert pk_columns[0].name == "id"

    def test_detects_not_null(self, sample_target_db):
        """Should detect NOT NULL constraint."""
        info = introspect_table("products")

        name_col = next(c for c in info.columns if c.name == "name")
        assert name_col.notnull is True

        desc_col = next(c for c in info.columns if c.name == "description")
        assert desc_col.notnull is False

    def test_detects_default_value(self, sample_target_db):
        """Should detect default values."""
        info = introspect_table("products")

        stock_col = next(c for c in info.columns if c.name == "stock")
        assert stock_col.default_value == "0"

        status_col = next(c for c in info.columns if c.name == "status")
        assert status_col.default_value == "'active'"

    def test_detects_foreign_keys(self, sample_target_db):
        """Should detect foreign keys."""
        info = introspect_table("products")

        assert len(info.foreign_keys) >= 1
        fk = info.foreign_keys[0]
        assert fk.table == "categories"
        assert fk.from_col == "category_id"
        assert fk.to_col == "id"

    def test_detects_column_types(self, sample_target_db):
        """Should detect column types."""
        info = introspect_table("products")

        id_col = next(c for c in info.columns if c.name == "id")
        assert "INTEGER" in id_col.type.upper()

        name_col = next(c for c in info.columns if c.name == "name")
        assert "TEXT" in name_col.type.upper()

        price_col = next(c for c in info.columns if c.name == "price")
        assert "REAL" in price_col.type.upper()

    def test_counts_rows(self, sample_target_db):
        """Should count rows in table."""
        info = introspect_table("products")
        assert info.row_count >= 1  # We inserted one product


class TestGetAllTables:
    """Tests for get_all_tables function."""

    def test_returns_all_tables(self, sample_target_db):
        """Should return all table names."""
        tables = get_all_tables()

        assert "products" in tables
        assert "categories" in tables
        assert "tasks" in tables
        assert "employees" in tables

    def test_excludes_sqlite_internal_tables(self, sample_target_db):
        """Should exclude sqlite internal tables."""
        tables = get_all_tables()

        for table in tables:
            assert not table.startswith("sqlite_")

    def test_returns_sorted_list(self, sample_target_db):
        """Should return sorted table names."""
        tables = get_all_tables()
        assert tables == sorted(tables)


class TestIntrospectAllTables:
    """Tests for introspect_all_tables function."""

    def test_returns_list_of_table_info(self, sample_target_db):
        """Should return list of TableInfo objects."""
        tables = introspect_all_tables()

        assert len(tables) >= 4
        for table in tables:
            assert isinstance(table, TableInfo)

    def test_all_tables_have_columns(self, sample_target_db):
        """All tables should have at least one column."""
        tables = introspect_all_tables()

        for table in tables:
            assert len(table.columns) > 0


class TestCacheTableMetadata:
    """Tests for cache_table_metadata function."""

    def test_caches_metadata(self, initialized_system_db, sample_target_db):
        """Should cache metadata in system database."""
        cache_table_metadata()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM table_metadata")
            count = cursor.fetchone()[0]
            assert count >= 4

    def test_clears_existing_cache(self, initialized_system_db, sample_target_db):
        """Should clear existing cache before caching."""
        cache_table_metadata()
        cache_table_metadata()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM table_metadata")
            count = cursor.fetchone()[0]
            # Should not have duplicates
            assert count >= 4 and count < 10

    def test_stores_columns_as_json(self, initialized_system_db, sample_target_db):
        """Should store columns as JSON."""
        cache_table_metadata()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT columns_json FROM table_metadata WHERE table_name = 'products'")
            row = cursor.fetchone()
            columns = json.loads(row['columns_json'])
            assert len(columns) > 0
            assert 'name' in columns[0]

    def test_stores_foreign_keys_as_json(self, initialized_system_db, sample_target_db):
        """Should store foreign keys as JSON."""
        cache_table_metadata()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT foreign_keys_json FROM table_metadata WHERE table_name = 'products'")
            row = cursor.fetchone()
            fks = json.loads(row['foreign_keys_json'])
            assert len(fks) >= 1


class TestGetCachedMetadata:
    """Tests for get_cached_metadata function."""

    def test_returns_cached_metadata(self, initialized_system_db, sample_target_db):
        """Should return cached metadata."""
        cache_table_metadata()
        metadata = get_cached_metadata()

        assert len(metadata) >= 4
        table_names = [m['table_name'] for m in metadata]
        assert 'products' in table_names

    def test_metadata_structure(self, initialized_system_db, sample_target_db):
        """Should return metadata with correct structure."""
        cache_table_metadata()
        metadata = get_cached_metadata()

        for m in metadata:
            assert 'table_name' in m
            assert 'row_count' in m
            assert 'columns' in m
            assert 'foreign_keys' in m

    def test_returns_sorted_by_table_name(self, initialized_system_db, sample_target_db):
        """Should return metadata sorted by table name."""
        cache_table_metadata()
        metadata = get_cached_metadata()

        table_names = [m['table_name'] for m in metadata]
        assert table_names == sorted(table_names)


class TestClearMetadataCache:
    """Tests for clear_metadata_cache function."""

    def test_clears_table_metadata(self, initialized_system_db, sample_target_db):
        """Should clear table_metadata table."""
        cache_table_metadata()
        clear_metadata_cache()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM table_metadata")
            assert cursor.fetchone()[0] == 0

    def test_clears_column_semantics(self, initialized_system_db, sample_target_db):
        """Should clear column_semantics table."""
        # First add some semantics
        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO column_semantics (table_name, column_name, semantic_type) VALUES (?, ?, ?)",
                ("test", "col", "created_at")
            )
            conn.commit()

        clear_metadata_cache()

        with initialized_system_db.get_system_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM column_semantics")
            assert cursor.fetchone()[0] == 0
