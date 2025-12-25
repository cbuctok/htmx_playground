# CLAUDE.md - AI Assistant Guide for SQLite Admin & Dashboard System

> **Last Updated**: 2025-12-25
> **Project**: SQLite Admin & Dashboard System
> **Tech Stack**: FastAPI + HTMX + SQLite + Jinja2

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Codebase Structure](#codebase-structure)
4. [Key Concepts](#key-concepts)
5. [Development Workflows](#development-workflows)
6. [Code Conventions](#code-conventions)
7. [Common Tasks](#common-tasks)
8. [Important Warnings](#important-warnings)

---

## Project Overview

### What This Is

A rapid demo and internal showcase tool for SQLite database administration with a server-rendered HTML + HTMX interface. The application automatically discovers SQLite databases, introspects their schema, and provides CRUD operations with auto-generated forms.

### Primary Purpose

- **Demo/Showcase Application**: Explicitly built for demonstration, NOT production use
- **Database Administration**: CRUD operations on any SQLite database
- **Schema Introspection**: Automatic discovery of tables, columns, relationships
- **Semantic Intelligence**: Infers column intent (timestamps, user references, status fields)
- **Dashboard Generation**: Auto-generated and custom dashboards

### Critical Security Warning

**DO NOT USE IN PRODUCTION!** This application is intentionally insecure:
- Plaintext passwords (no hashing)
- Cookie-based sessions (minimal security)
- No authentication hardening
- No isolation guarantees
- SQL injection vulnerabilities in some areas

When modifying this code, do NOT attempt to make it "production-ready" unless explicitly requested.

---

## Architecture

### Two-Database System

The application uses a dual-database architecture:

1. **System Database** (`data/system.db`)
   - Managed by the application
   - Stores: users, dashboards, views, column_semantics, app_config, ui_preferences, table_metadata
   - Created automatically on startup via `app/database.py:init_system_db()`

2. **Target Database** (`data/uploaded_db/*.db`)
   - User-provided SQLite database
   - Read and modified by CRUD operations
   - Discovered on startup via `app/discovery.py:load_target_database()`

### Database Discovery Rules

Located in `app/discovery.py:load_target_database()`:

| Condition | Behavior |
|-----------|----------|
| No `.db` files found | **Fail fast** - abort startup with error |
| Exactly one `.db` file | Load it automatically |
| Multiple `.db` files | Load most recently modified, show warning banner |

### Request Flow

```
HTTP Request
    ↓
FastAPI Middleware (main.py:96)
    ↓
Authentication Check (app/auth.py:validate_session)
    ↓
Route Handler (app/routes/*.py)
    ↓
CRUD/Business Logic (app/crud.py, app/introspection.py)
    ↓
Database Operations (app/database.py:DatabaseManager)
    ↓
Jinja2 Template Rendering (templates/)
    ↓
HTML Response (with HTMX attributes for interactivity)
```

### Lifecycle Hooks

The application uses FastAPI's lifespan context manager in `main.py:34-78`:

**Startup sequence:**
1. Initialize system database
2. Discover and load target database
3. Cache schema metadata
4. Detect column semantics
5. Create default dashboard if needed

**Shutdown:**
- Simple cleanup (database connections auto-close via context managers)

---

## Codebase Structure

```
htmx_playground/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── config.py                # Configuration constants (paths, secrets)
│   ├── database.py              # DatabaseManager singleton, connection handling
│   ├── discovery.py             # Target database discovery logic
│   ├── introspection.py         # Schema introspection (tables, columns, FKs)
│   ├── semantics.py             # Column semantic type detection
│   ├── crud.py                  # CRUD engine with auto-population
│   ├── auth.py                  # Session-based authentication
│   ├── branding.py              # Theming and UI preferences
│   ├── dashboards.py            # Dashboard management
│   └── routes/
│       ├── __init__.py
│       ├── auth.py              # Login/logout endpoints
│       ├── tables.py            # Table CRUD endpoints
│       ├── dashboards.py        # Dashboard view endpoints
│       └── admin.py             # Admin panel endpoints
├── templates/
│   ├── base.html                # Base layout with header/footer
│   ├── login.html               # Login page
│   ├── admin/                   # Admin panel templates
│   ├── dashboards/              # Dashboard view templates
│   ├── tables/                  # Table CRUD templates
│   ├── partials/                # HTMX partial templates
│   └── errors/                  # Error page templates
├── static/
│   └── css/                     # Static stylesheets
├── data/
│   ├── system.db                # System database (auto-created)
│   └── uploaded_db/             # Target databases directory
├── main.py                      # Application entry point
├── create_sample_db.py          # Sample database generator
└── requirements.txt             # Python dependencies
```

### Key Modules

| Module | Purpose | Key Functions/Classes |
|--------|---------|----------------------|
| `config.py` | Configuration | `BASE_DIR`, `DATA_DIR`, `SYSTEM_DB_PATH`, `SECRET_KEY` |
| `database.py` | Connection management | `DatabaseManager` (singleton), `get_system_connection()`, `get_target_connection()` |
| `discovery.py` | DB discovery | `load_target_database()`, `DatabaseDiscoveryError` |
| `introspection.py` | Schema analysis | `introspect_table()`, `get_all_tables()`, `cache_table_metadata()` |
| `semantics.py` | Column semantics | `detect_semantic_type()`, `cache_column_semantics()`, `get_table_semantics()` |
| `crud.py` | CRUD operations | `list_rows()`, `get_row()`, `create_row()`, `update_row()`, `delete_row()` |
| `auth.py` | Authentication | `create_session()`, `validate_session()`, `User` dataclass |
| `branding.py` | Theming | `get_app_config()`, `get_ui_preferences()`, `get_css_variables()` |

---

## Key Concepts

### 1. Column Semantics Detection

**Location**: `app/semantics.py`

The system automatically detects column intent based on naming patterns:

| Semantic Type | Example Columns | Behavior |
|--------------|----------------|----------|
| `created_at` | created_at, created_on, date_created | Auto-populate on INSERT with current timestamp |
| `updated_at` | updated_at, modified_at, last_modified | Auto-populate on INSERT/UPDATE with current timestamp |
| `deleted_at` | deleted_at, soft_deleted | Enable soft delete (UPDATE instead of DELETE) |
| `created_by` | created_by, author, creator | Auto-populate with current username |
| `updated_by` | updated_by, modified_by, editor | Auto-populate with current username |
| `status` | status, state, is_active | (Reserved for future use) |

**Pattern Matching**: Case-insensitive regex patterns in `SEMANTIC_PATTERNS` dict (lines 10-65)

**Detection Flow**:
1. On startup: `cache_column_semantics()` scans all tables
2. Stores results in `system.db.column_semantics` table
3. CRUD operations query semantics to auto-populate fields

### 2. Soft Delete

**Location**: `app/crud.py:delete_row()` (lines 267-300)

If a table has a `deleted_at` semantic column:
- DELETE operations become UPDATE operations
- Sets `deleted_at = current_timestamp` instead of removing row
- List queries filter out soft-deleted rows by default

**Implementation**:
```python
deleted_col = get_soft_delete_column(table_name)
if deleted_col:
    # Soft delete: UPDATE table SET deleted_at = NOW()
else:
    # Hard delete: DELETE FROM table
```

### 3. Auto-Population

**Location**: `app/crud.py:create_row()` and `update_row()`

During INSERT/UPDATE operations, semantic columns are automatically populated:

```python
# app/crud.py:203-211
for col, sem_type in semantics.items():
    if sem_type == 'created_at' and col not in data:
        data[col] = now
    elif sem_type == 'updated_at' and col not in data:
        data[col] = now
    elif sem_type == 'created_by' and col not in data and current_user:
        data[col] = current_user
    # ... etc
```

### 4. Form Field Generation

**Location**: `app/crud.py:get_form_fields()` (lines 69-101)

Forms are dynamically generated based on:
- Column data types (INTEGER → number, TEXT → text, etc.)
- Semantic types (created_at → hidden, updated_at → hidden)
- Mode (create vs edit)
- Constraints (NOT NULL → required)

**Visibility Rules**:
- Primary keys: Hidden on create, hidden on edit
- `created_at`: Hidden on create, hidden on edit (immutable)
- `updated_at`: Hidden on create, hidden on edit (auto-updated)
- `created_by`/`updated_by`: Auto-filled (can be shown or hidden)

### 5. HTMX Integration

**Location**: Templates and route handlers

The application uses HTMX for dynamic updates without full page reloads:

**Pattern**:
```html
<!-- Full page request -->
<a href="/tables/users">View Users</a>

<!-- HTMX partial request -->
<button hx-get="/tables/users" hx-target="#content" hx-swap="innerHTML">
    Load Users
</button>
```

**Route Detection**:
```python
# app/routes/tables.py:88-91
if request.headers.get("HX-Request"):
    return templates.TemplateResponse("partials/table_rows.html", context)
return templates.TemplateResponse("tables/view.html", context)
```

### 6. Metadata Caching

**Location**: `app/introspection.py:cache_table_metadata()`

Schema introspection is expensive, so results are cached in `system.db`:

**Cache Storage**:
- Table: `table_metadata`
- Columns: `table_name`, `row_count`, `columns_json`, `foreign_keys_json`

**Cache Invalidation**:
- On database reload
- Manual admin action
- Database replacement

---

## Development Workflows

### Adding a New Route

1. **Choose the appropriate router** in `app/routes/`:
   - `auth.py` for login/logout
   - `tables.py` for table CRUD
   - `dashboards.py` for dashboard views
   - `admin.py` for admin functions

2. **Define the route handler**:
   ```python
   @router.get("/your-endpoint", response_class=HTMLResponse)
   async def your_handler(request: Request):
       user = request.state.user  # Current user (set by middleware)
       # ... logic ...
       return templates.TemplateResponse("your_template.html", context)
   ```

3. **Create template** in `templates/` directory

4. **Add HTMX support** if needed:
   ```python
   if request.headers.get("HX-Request"):
       return templates.TemplateResponse("partials/your_partial.html", context)
   ```

### Adding a New Semantic Type

1. **Add pattern to `app/semantics.py`**:
   ```python
   SEMANTIC_PATTERNS = {
       'your_type': [
           r'^your[-_]?pattern$',
           r'^another[-_]?pattern$',
       ],
   }
   ```

2. **Implement behavior in `app/crud.py`**:
   - `create_row()` - auto-populate on INSERT
   - `update_row()` - auto-populate on UPDATE
   - `get_form_fields()` - control visibility
   - `should_show_on_create()` - form visibility rules
   - `should_show_on_edit()` - form visibility rules

3. **Update documentation** (README.md and this file)

### Adding Database Tables (System DB)

1. **Add table creation** in `app/database.py:init_system_db()`:
   ```python
   cursor.execute('''
       CREATE TABLE IF NOT EXISTS your_table (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           your_column TEXT NOT NULL
       )
   ''')
   ```

2. **Create helper functions** to interact with the table

3. **Seed default data** if needed (in same function)

### Running the Application

**Development**:
```bash
# Install dependencies
pip install -r requirements.txt

# Create sample database
python create_sample_db.py

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or use the shortcut
python main.py
```

**Adding Your Own Database**:
```bash
# Copy database to target directory
cp /path/to/your.db data/uploaded_db/

# Restart application (it will discover on startup)
```

### Testing Changes

**Manual Testing Workflow**:
1. Start application
2. Login with default credentials (admin/password)
3. Navigate to affected feature
4. Test CRUD operations
5. Check browser console for errors
6. Verify HTMX requests in Network tab

**No Automated Tests**: This is a demo application without test coverage

---

## Code Conventions

### Python Style

- **PEP 8 compliant** (mostly)
- **Type hints** where helpful: `def func(arg: str) -> int:`
- **Docstrings** for modules and complex functions (Google style)
- **Context managers** for database connections: `with db.get_connection():`

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Functions | snake_case | `get_table_metadata()` |
| Classes | PascalCase | `DatabaseManager` |
| Constants | UPPER_SNAKE | `SYSTEM_DB_PATH` |
| Private | _prefix | `_instance` |
| Modules | snake_case | `introspection.py` |
| Templates | snake_case.html | `table_view.html` |
| Routes | kebab-case | `/tables/schema` |

### Database Patterns

**Connection Management**:
```python
# GOOD - Uses context manager
with db.get_system_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    result = cursor.fetchall()
    conn.commit()  # Only for writes
# Connection auto-closes

# BAD - Manual connection management
conn = get_connection()
cursor = conn.cursor()
# ... forgot to close!
```

**SQL String Formatting**:
```python
# GOOD - Parameterized queries for user input
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# ACCEPTABLE - String formatting for table/column names (validated)
cursor.execute(f'SELECT * FROM "{table_name}" WHERE "{column}" = ?', (value,))

# BAD - String interpolation with user input (SQL injection)
cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")
```

**Row Access**:
```python
# Set row factory for dict-like access
conn.row_factory = sqlite3.Row
cursor.execute("SELECT * FROM users")
row = cursor.fetchone()
username = row['username']  # Dict-like access
```

### Template Patterns

**Base Template Inheritance**:
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
<head>{% block head %}...{% endblock %}</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>

<!-- templates/your_page.html -->
{% extends "base.html" %}
{% block content %}
    Your content here
{% endblock %}
```

**HTMX Partial Templates**:
```html
<!-- Full page: templates/tables/view.html -->
{% extends "base.html" %}
{% block content %}
    <div id="table-content">
        {% include "partials/table_rows.html" %}
    </div>
{% endblock %}

<!-- Partial: templates/partials/table_rows.html -->
<!-- No base.html extension, just the fragment -->
<table>
    {% for row in rows %}
        <tr>...</tr>
    {% endfor %}
</table>
```

### FastAPI Patterns

**Route Dependencies**:
```python
# Current user is injected via middleware (main.py:96-114)
# Access via request.state.user

def get_current_user(request: Request) -> Optional[User]:
    return getattr(request.state, 'user', None)

@router.get("/endpoint")
async def handler(request: Request):
    user = get_current_user(request)
    # ... use user ...
```

**Response Types**:
```python
# HTML responses
@router.get("/page", response_class=HTMLResponse)
async def page(request: Request):
    return templates.TemplateResponse("page.html", {...})

# Redirects (HTMX-aware)
if request.headers.get("HX-Request"):
    return HTMLResponse(content="", headers={"HX-Redirect": "/path"})
return RedirectResponse(url="/path", status_code=303)

# HTMX delete response
return HTMLResponse(content="")  # Removes element from DOM
```

---

## Common Tasks

### 1. Add a New Admin Feature

**File**: `app/routes/admin.py`

```python
@router.get("/admin/your-feature", response_class=HTMLResponse)
async def your_feature(request: Request):
    user = request.state.user
    if user.role != 'admin':
        return templates.TemplateResponse("errors/403.html", {...}, status_code=403)

    # ... admin logic ...
    return templates.TemplateResponse("admin/your_feature.html", {...})
```

### 2. Add a New Column to System Database

**File**: `app/database.py`

1. Add migration logic in `init_system_db()`:
   ```python
   # Check if column exists
   cursor.execute("PRAGMA table_info(your_table)")
   columns = [row['name'] for row in cursor.fetchall()]

   if 'new_column' not in columns:
       cursor.execute("ALTER TABLE your_table ADD COLUMN new_column TEXT")
       conn.commit()
   ```

2. Update related functions to use the new column

### 3. Customize Dashboard Layout

**File**: `app/dashboards.py` and `templates/dashboards/*.html`

1. Create dashboard configuration:
   ```python
   def create_custom_dashboard(name: str, config: dict):
       db = get_db_manager()
       with db.get_system_connection() as conn:
           cursor = conn.cursor()
           cursor.execute(
               "INSERT INTO dashboards (name, config_json) VALUES (?, ?)",
               (name, json.dumps(config))
           )
           conn.commit()
   ```

2. Create template in `templates/dashboards/`

3. Add route in `app/routes/dashboards.py`

### 4. Add Branding/Theming Options

**File**: `app/branding.py`

1. Add config key to defaults in `database.py:init_system_db()`:
   ```python
   default_config = [
       ('your_setting', 'default_value'),
   ]
   ```

2. Update `get_css_variables()` if it's a CSS property:
   ```python
   css += f"--your-property: {config['your_setting']};\n"
   ```

3. Use in templates:
   ```html
   <div style="background: var(--your-property)">...</div>
   ```

### 5. Add Input Type for Specific Columns

**File**: `app/crud.py:get_input_type()`

```python
def get_input_type(column: ColumnInfo, semantic_type: Optional[str] = None) -> str:
    col_type = column.type.upper()

    # Add your custom logic
    if column.name.lower() == 'email':
        return 'email'
    if column.name.lower() == 'phone':
        return 'tel'

    # ... existing logic ...
```

---

## Important Warnings

### Security

**DO NOT**:
- Use this application in production
- Store real user data
- Connect to databases with sensitive information
- Expose this application to the internet
- Use this as a template for production apps without major security overhaul

**Specific Vulnerabilities**:
1. **Authentication**: Plaintext passwords in `app/auth.py`
2. **Session Management**: Weak cookie signing in `app/config.py`
3. **SQL Injection**: Some dynamic SQL in `app/crud.py` and `app/introspection.py`
4. **No CSRF Protection**: Forms lack CSRF tokens
5. **No Rate Limiting**: Login attempts unlimited
6. **No Input Validation**: Limited sanitization of user input

### Database Replacement

When replacing the target database (`data/uploaded_db/*.db`):

**Automatically Cleared**:
- Table metadata cache
- Column semantics
- Dashboards
- Views

**Preserved**:
- Users (in system.db)
- Branding settings
- UI preferences

**Process**:
1. Replace `.db` file in `data/uploaded_db/`
2. Restart application
3. Caches rebuild on startup

### Performance Considerations

- **No query optimization**: Full table scans on search
- **No connection pooling**: New connection per request
- **No caching layer**: Metadata cached but data is not
- **No pagination optimization**: Counts entire table on each page load

**Acceptable for**:
- Small databases (< 1000 rows per table)
- Internal tools
- Development/testing

**Not acceptable for**:
- Large databases (> 10,000 rows)
- High-traffic applications
- Production workloads

### File Modifications

**Safe to Modify**:
- Templates (won't break functionality)
- CSS styles
- Default configurations
- Sample database generator

**Modify with Care**:
- Route handlers (ensure HTMX compatibility)
- CRUD functions (semantic behavior is complex)
- Database schema (migrations needed)

**Do Not Modify Without Deep Understanding**:
- `DatabaseManager` singleton pattern
- Startup lifecycle in `main.py:lifespan()`
- Middleware chain in `main.py`
- Database discovery logic in `discovery.py`

---

## Quick Reference

### Default Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | password | admin |
| user1 | password | user |
| user2 | password | user |

### Important File Locations

| Purpose | Location |
|---------|----------|
| System database | `data/system.db` |
| Target databases | `data/uploaded_db/*.db` |
| Static files | `static/` |
| Templates | `templates/` |
| Configuration | `app/config.py` |
| Entry point | `main.py` |

### Useful Commands

```bash
# Run application
python main.py

# Generate sample database
python create_sample_db.py

# View SQLite database
sqlite3 data/system.db ".schema"

# Check target database
sqlite3 data/uploaded_db/*.db ".tables"

# Clear cache (delete system.db and restart)
rm data/system.db && python main.py
```

### Tech Stack Reference

| Component | Version | Purpose |
|-----------|---------|---------|
| FastAPI | 0.109.0 | Web framework |
| Uvicorn | 0.27.0 | ASGI server |
| Jinja2 | 3.1.3 | Template engine |
| HTMX | (CDN) | Frontend interactivity |
| SQLite | 3.x | Database |
| itsdangerous | 2.1.2 | Session signing |

---

## Getting Help

**When modifying this codebase:**

1. **Read the code first** - Most behavior is self-documenting
2. **Check this file** - Conventions and patterns documented here
3. **Read README.md** - User-facing feature documentation
4. **Inspect templates** - UI/UX patterns visible in HTML
5. **Test locally** - Always run and test changes manually

**Common Gotchas:**

- Database connections use context managers - don't forget `with` statement
- HTMX requests need partial templates - check `HX-Request` header
- Semantic column detection is case-insensitive - patterns use regex
- Primary key detection falls back to first column if no PK defined
- Soft delete queries filter by `deleted_at IS NULL` automatically

---

**End of CLAUDE.md**
