"""
SQLite Admin & Dashboard System

WARNING: This is a demo application - explicitly insecure by design!
- Plaintext passwords
- No authentication hardening
- No isolation guarantees

DO NOT USE IN PRODUCTION!
"""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import SESSION_COOKIE_NAME
from app.database import init_system_db, get_db_manager
from app.discovery import load_target_database, DatabaseDiscoveryError
from app.introspection import cache_table_metadata
from app.semantics import cache_column_semantics
from app.dashboards import reset_dashboards
from app.story import cache_dependency_graph, initialize_story_steps
from app.auth import validate_session
from app.branding import get_app_config, get_ui_preferences, get_css_variables

from app.routes.auth import router as auth_router
from app.routes.tables import router as tables_router
from app.routes.dashboards import router as dashboards_router
from app.routes.admin import router as admin_router
from app.routes.story import router as story_router
from app.routes.views import router as views_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("=" * 60)
    print("SQLite Admin & Dashboard System")
    print("WARNING: Demo only - insecure by design!")
    print("=" * 60)

    # Initialize system database
    init_system_db()
    print("[OK] System database initialized")

    # Discover and load target database
    try:
        db_name, multiple_found, available_dbs = load_target_database()
        if multiple_found:
            print(f"[!] Multiple databases detected: {available_dbs}")
            print(f"[!] Loaded most recently modified: {db_name}")
        else:
            print(f"[OK] Target database loaded: {db_name}")
    except DatabaseDiscoveryError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # Cache schema metadata
    cache_table_metadata()
    print("[OK] Schema metadata cached")

    # Detect column semantics
    cache_column_semantics()
    print("[OK] Column semantics detected")

    # Create default dashboard if none exist
    reset_dashboards()
    print("[OK] Default dashboard created")

    # Initialize Story Mode (dependency graph and steps)
    cache_dependency_graph()
    initialize_story_steps()
    print("[OK] Story Mode initialized")

    print("=" * 60)
    print("Default credentials: admin/password, user1/password, user2/password")
    print("=" * 60)

    yield

    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="SQLite Admin",
    description="Demo SQLite Admin & Dashboard System",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


# Middleware for authentication
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check authentication for protected routes."""
    # Public routes
    public_paths = ["/login", "/static", "/favicon.ico"]

    if any(request.url.path.startswith(p) for p in public_paths):
        return await call_next(request)

    # Check session cookie
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if token:
        user = validate_session(token)
        if user:
            request.state.user = user
            return await call_next(request)

    # Redirect to login
    return RedirectResponse(url="/login", status_code=303)


# Template context processor
@app.middleware("http")
async def template_context_middleware(request: Request, call_next):
    """Add common context to all requests."""
    response = await call_next(request)
    return response


# Include routers
app.include_router(auth_router)
app.include_router(tables_router)
app.include_router(dashboards_router)
app.include_router(admin_router)
app.include_router(story_router)
app.include_router(views_router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - redirect to default dashboard."""
    return RedirectResponse(url="/dashboards/default", status_code=303)


@app.get("/css/theme.css", response_class=HTMLResponse)
async def dynamic_theme_css(request: Request):
    """Generate dynamic CSS based on branding settings."""
    css = get_css_variables()
    return HTMLResponse(content=css, media_type="text/css")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
