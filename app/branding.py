"""Branding and theming system."""
from typing import Optional
from dataclasses import dataclass

from app.database import get_db_manager


@dataclass
class AppBranding:
    """Application branding configuration."""
    app_name: str
    logo_path: str
    primary_color: str
    secondary_color: str
    background_color: str
    accent_color: str


@dataclass
class UIPreferences:
    """UI preferences configuration."""
    date_format: str
    page_size: int
    theme: str


def get_app_config() -> AppBranding:
    """Get the current application branding configuration."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM app_config")
        config = {row['key']: row['value'] for row in cursor.fetchall()}

    return AppBranding(
        app_name=config.get('app_name', 'SQLite Admin'),
        logo_path=config.get('logo_path', ''),
        primary_color=config.get('primary_color', '#3b82f6'),
        secondary_color=config.get('secondary_color', '#64748b'),
        background_color=config.get('background_color', '#f8fafc'),
        accent_color=config.get('accent_color', '#10b981'),
    )


def update_app_config(
    app_name: Optional[str] = None,
    logo_path: Optional[str] = None,
    primary_color: Optional[str] = None,
    secondary_color: Optional[str] = None,
    background_color: Optional[str] = None,
    accent_color: Optional[str] = None,
):
    """Update application branding configuration."""
    db = get_db_manager()

    updates = {}
    if app_name is not None:
        updates['app_name'] = app_name
    if logo_path is not None:
        updates['logo_path'] = logo_path
    if primary_color is not None:
        updates['primary_color'] = primary_color
    if secondary_color is not None:
        updates['secondary_color'] = secondary_color
    if background_color is not None:
        updates['background_color'] = background_color
    if accent_color is not None:
        updates['accent_color'] = accent_color

    if not updates:
        return

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        for key, value in updates.items():
            cursor.execute(
                "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()


def get_ui_preferences() -> UIPreferences:
    """Get the current UI preferences."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM ui_preferences")
        prefs = {row['key']: row['value'] for row in cursor.fetchall()}

    return UIPreferences(
        date_format=prefs.get('date_format', '%Y-%m-%d %H:%M:%S'),
        page_size=int(prefs.get('page_size', '25')),
        theme=prefs.get('theme', 'light'),
    )


def update_ui_preferences(
    date_format: Optional[str] = None,
    page_size: Optional[int] = None,
    theme: Optional[str] = None,
):
    """Update UI preferences."""
    db = get_db_manager()

    updates = {}
    if date_format is not None:
        updates['date_format'] = date_format
    if page_size is not None:
        updates['page_size'] = str(page_size)
    if theme is not None:
        updates['theme'] = theme

    if not updates:
        return

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        for key, value in updates.items():
            cursor.execute(
                "INSERT OR REPLACE INTO ui_preferences (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()


def get_css_variables() -> str:
    """Generate CSS variables from branding configuration."""
    branding = get_app_config()
    prefs = get_ui_preferences()

    return f"""
    :root {{
        --primary-color: {branding.primary_color};
        --secondary-color: {branding.secondary_color};
        --background-color: {branding.background_color};
        --accent-color: {branding.accent_color};
        --text-color: #1e293b;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --error-color: #ef4444;
        --success-color: #22c55e;
        --warning-color: #f59e0b;
    }}

    [data-theme="dark"] {{
        --background-color: #0f172a;
        --text-color: #f1f5f9;
        --text-muted: #94a3b8;
        --border-color: #334155;
    }}
    """
