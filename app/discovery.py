"""Target database discovery and loading."""
import os
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_DIR, SYSTEM_DB_NAME
from app.database import get_db_manager


class DatabaseDiscoveryError(Exception):
    """Raised when database discovery fails."""
    pass


def discover_target_database() -> tuple[Path, str, bool, list[str]]:
    """
    Discover and load the target database.

    Returns:
        Tuple of (db_path, db_name, multiple_found, available_dbs)

    Raises:
        DatabaseDiscoveryError: If no database is found
    """
    # Scan for .db files
    db_files = []
    for file in UPLOAD_DIR.iterdir():
        if file.is_file() and file.suffix == '.db' and file.name != SYSTEM_DB_NAME:
            db_files.append(file)

    if not db_files:
        raise DatabaseDiscoveryError(
            f"No target database found in {UPLOAD_DIR}. "
            "Please add a .db file to the uploaded_db directory."
        )

    available_dbs = [f.name for f in db_files]
    multiple_found = len(db_files) > 1

    if multiple_found:
        # Load most recently modified
        db_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    target_db = db_files[0]
    return target_db, target_db.name, multiple_found, available_dbs


def load_target_database() -> tuple[str, bool, list[str]]:
    """
    Discover and load the target database into the manager.

    Returns:
        Tuple of (db_name, multiple_found, available_dbs)
    """
    db_path, db_name, multiple_found, available_dbs = discover_target_database()

    db_manager = get_db_manager()
    db_manager.set_target_db(db_path, db_name)
    db_manager.multiple_dbs_detected = multiple_found
    db_manager.available_dbs = available_dbs

    return db_name, multiple_found, available_dbs


def switch_target_database(db_name: str) -> bool:
    """
    Switch to a different target database.

    Returns:
        True if successful, False if database not found
    """
    db_path = UPLOAD_DIR / db_name

    if not db_path.exists() or db_name == SYSTEM_DB_NAME:
        return False

    db_manager = get_db_manager()
    db_manager.set_target_db(db_path, db_name)

    return True


def get_available_databases() -> list[str]:
    """Get list of available database files."""
    db_files = []
    for file in UPLOAD_DIR.iterdir():
        if file.is_file() and file.suffix == '.db' and file.name != SYSTEM_DB_NAME:
            db_files.append(file.name)
    return sorted(db_files)
