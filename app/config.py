"""Application configuration."""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploaded_db"

# Database paths
SYSTEM_DB_PATH = DATA_DIR / "system.db"
SYSTEM_DB_NAME = "system.db"

# Session config
SECRET_KEY = "demo-insecure-secret-key-do-not-use-in-production"
SESSION_COOKIE_NAME = "session"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
