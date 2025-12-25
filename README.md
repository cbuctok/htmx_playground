# SQLite Admin & Dashboard System

> **WARNING: This is a demo application - explicitly insecure by design!**
>
> - Plaintext passwords (no hashing)
> - Cookie-based session (minimal security)
> - No authentication hardening
> - No isolation guarantees
>
> **DO NOT USE IN PRODUCTION!**

A rapid demo and internal showcase tool for SQLite database administration with a server-rendered HTML + HTMX interface.

## Features

- **Database Discovery**: Automatically discovers and loads SQLite databases from `/data/uploaded_db/`
- **Schema Introspection**: Enumerates tables, columns, foreign keys, and row counts
- **Column Semantics Detection**: Infers column intent (timestamps, user references, status fields)
- **CRUD Operations**: Create, read, update, delete with auto-generated forms
- **Dashboards**: Auto-generated and custom dashboards
- **Branding**: Customizable app name, logo, and color palette
- **User Management**: Admin and user roles

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add a target database

Place a `.db` file in `data/uploaded_db/`:

```bash
# Use the included sample database
python create_sample_db.py

# Or copy your own database
cp /path/to/your/database.db data/uploaded_db/
```

### 3. Run the application

```bash
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Login

Navigate to http://localhost:8000 and login with default credentials:

| Username | Password | Role |
|----------|----------|------|
| admin | password | Admin |
| user1 | password | User |
| user2 | password | User |

## Database Loading Rules

On startup, the application scans `data/uploaded_db/` for `.db` files:

| Condition | Behavior |
|-----------|----------|
| No target DB found | Fail fast - abort startup with error |
| Exactly one target DB | Load it |
| Multiple target DBs | Load most recently modified |

When multiple databases are detected, a banner displays:
> "Multiple databases detected. Loaded latest modified: `<filename>`"

The active database name is always visible in the header/footer.

## Database Replacement

Replacing the target database triggers a reset event:

**Automatically cleared:**
- Cached schema metadata
- Dashboards and generated views
- Column semantics

**Preserved:**
- Users
- Branding settings
- UI preferences

## Column Semantics Detection

The system infers column intent to enhance UX:

| Semantic Type | Example Column Names |
|--------------|---------------------|
| `created_at` | created_at, created_on, date_created |
| `updated_at` | updated_at, modified_at, last_modified |
| `deleted_at` | deleted_at, soft_deleted |
| `created_by` | created_by, author, creator |
| `updated_by` | updated_by, modified_by, editor |
| `status` | status, state, is_active |

### Semantic Behaviors

- **Auto-populate timestamps**: `created_at`/`updated_at` are auto-filled with current time
- **Auto-fill user references**: `created_by`/`updated_by` are auto-filled with current user
- **Soft delete**: If `deleted_at` exists, delete operations set this timestamp instead of removing rows
- **Form hiding**: Semantic columns are hidden or collapsed in forms as appropriate

## System Database

The system uses a separate SQLite database (`data/system.db`) with:

- `users` - User accounts with plaintext passwords
- `dashboards` - Saved dashboard configurations
- `views` - Saved SQL views
- `column_semantics` - Cached column semantics
- `app_config` - Branding settings
- `ui_preferences` - UI settings
- `table_metadata` - Cached table introspection

## Admin Features

Admins can:
- Manage users (create, edit, delete)
- Configure branding (app name, logo, colors)
- Set UI preferences (theme, page size, date format)
- Reload schema metadata
- Reset dashboards and views
- Clear metadata cache
- Switch between available databases

## Project Structure

```
htmx_playground/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration settings
│   ├── database.py        # Database connection management
│   ├── discovery.py       # Target DB discovery
│   ├── introspection.py   # Schema introspection
│   ├── semantics.py       # Column semantics detection
│   ├── crud.py            # CRUD operations
│   ├── auth.py            # Authentication
│   ├── branding.py        # Branding/theming
│   ├── dashboards.py      # Dashboard management
│   └── routes/
│       ├── auth.py        # Login/logout routes
│       ├── tables.py      # Table CRUD routes
│       ├── dashboards.py  # Dashboard routes
│       └── admin.py       # Admin routes
├── templates/             # Jinja2 templates
├── static/css/            # CSS styles
├── data/
│   ├── system.db          # System database (auto-created)
│   └── uploaded_db/       # Target databases go here
├── main.py                # Application entry point
├── create_sample_db.py    # Sample database generator
└── requirements.txt       # Python dependencies
```

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: Server-rendered HTML + HTMX
- **Database**: SQLite (system and target)
- **Templates**: Jinja2
- **Session**: itsdangerous for cookie signing

## Non-Goals

This is a demo application. The following are explicitly out of scope:

- Schema migrations
- Advanced analytics, joins, or semantic inference beyond light heuristics
- Frontend framework or SPA behavior
- Authentication hardening
- Isolation guarantees
- Bulk editing or inline spreadsheet UI
