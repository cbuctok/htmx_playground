"""Admin routes."""
from typing import Optional
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_all_users, create_user, update_user, delete_user
from app.branding import get_app_config, update_app_config, get_ui_preferences, update_ui_preferences
from app.introspection import cache_table_metadata, clear_metadata_cache
from app.semantics import cache_column_semantics
from app.dashboards import reset_dashboards, reset_views
from app.discovery import get_available_databases, switch_target_database
from app.database import get_db_manager

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


# Admin middleware check
def require_admin(request: Request):
    """Check if current user is admin."""
    user = getattr(request.state, 'user', None)
    if not user or not user.is_admin:
        return False
    return True


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    db = get_db_manager()

    return templates.TemplateResponse("admin/index.html", {
        "request": request,
        "current_db": db.target_db_name,
        "available_dbs": get_available_databases(),
    })


# User management

@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request):
    """List all users."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    users = get_all_users()

    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "users": users,
    })


@router.get("/users/new", response_class=HTMLResponse)
async def new_user_form(request: Request):
    """Render form for creating a new user."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("admin/user_form.html", {
        "request": request,
        "mode": "create",
        "user": None,
    })


@router.post("/users/new")
async def create_new_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
):
    """Create a new user."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    try:
        create_user(username, password, role)

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content="",
                headers={"HX-Redirect": "/admin/users"}
            )

        return RedirectResponse(url="/admin/users", status_code=303)

    except Exception as e:
        return templates.TemplateResponse("admin/user_form.html", {
            "request": request,
            "mode": "create",
            "user": {"username": username, "role": role},
            "error": str(e),
        }, status_code=400)


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(request: Request, user_id: int):
    """Render form for editing a user."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    users = get_all_users()
    user = next((u for u in users if u['id'] == user_id), None)

    if not user:
        return templates.TemplateResponse("errors/404.html", {
            "request": request,
            "message": f"User {user_id} not found",
        }, status_code=404)

    return templates.TemplateResponse("admin/user_form.html", {
        "request": request,
        "mode": "edit",
        "user": user,
    })


@router.post("/users/{user_id}/edit")
async def update_existing_user(
    request: Request,
    user_id: int,
    username: str = Form(None),
    password: str = Form(None),
    role: str = Form(None),
):
    """Update a user."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    update_user(user_id, username=username, password=password or None, role=role)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/admin/users"}
        )

    return RedirectResponse(url="/admin/users", status_code=303)


@router.delete("/users/{user_id}")
async def delete_existing_user(request: Request, user_id: int):
    """Delete a user."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    delete_user(user_id)

    if request.headers.get("HX-Request"):
        return HTMLResponse(content="")

    return RedirectResponse(url="/admin/users", status_code=303)


# Branding

@router.get("/branding", response_class=HTMLResponse)
async def branding_form(request: Request):
    """Branding settings form."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    config = get_app_config()
    prefs = get_ui_preferences()

    return templates.TemplateResponse("admin/branding.html", {
        "request": request,
        "config": config,
        "prefs": prefs,
    })


@router.post("/branding")
async def update_branding(
    request: Request,
    app_name: str = Form(None),
    logo_path: str = Form(None),
    primary_color: str = Form(None),
    secondary_color: str = Form(None),
    background_color: str = Form(None),
    accent_color: str = Form(None),
    date_format: str = Form(None),
    page_size: int = Form(None),
    theme: str = Form(None),
):
    """Update branding settings."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    update_app_config(
        app_name=app_name,
        logo_path=logo_path,
        primary_color=primary_color,
        secondary_color=secondary_color,
        background_color=background_color,
        accent_color=accent_color,
    )

    update_ui_preferences(
        date_format=date_format,
        page_size=page_size,
        theme=theme,
    )

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="alert alert-success">Settings saved successfully</div>',
        )

    return RedirectResponse(url="/admin/branding", status_code=303)


# Reset controls

@router.post("/reload-schema")
async def reload_schema(request: Request):
    """Reload schema from target database."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    cache_table_metadata()
    cache_column_semantics()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="alert alert-success">Schema reloaded successfully</div>',
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/reset-dashboards")
async def reset_all_dashboards(request: Request):
    """Reset all dashboards and views."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    reset_dashboards()
    reset_views()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="alert alert-success">Dashboards reset successfully</div>',
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/clear-cache")
async def clear_cache(request: Request):
    """Clear metadata cache."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    clear_metadata_cache()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="alert alert-success">Cache cleared successfully</div>',
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/switch-database")
async def switch_database(request: Request, database: str = Form(...)):
    """Switch to a different target database."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    if switch_target_database(database):
        # Reset metadata for new database
        clear_metadata_cache()
        cache_table_metadata()
        cache_column_semantics()
        reset_dashboards()
        reset_views()

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content="",
                headers={"HX-Redirect": "/"}
            )

        return RedirectResponse(url="/", status_code=303)

    return HTMLResponse(content="Database not found", status_code=404)
