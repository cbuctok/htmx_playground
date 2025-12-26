"""Views routes for the right-side sidebar."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db_manager
from app.dashboards import get_view, get_views_for_sidebar

router = APIRouter(prefix="/views")
templates = Jinja2Templates(directory="templates")


@router.get("/{view_id}", response_class=HTMLResponse)
async def show_view(request: Request, view_id: int):
    """Show a view (full page)."""
    view = get_view(view_id)

    if not view:
        return templates.TemplateResponse("errors/404.html", {
            "request": request,
            "message": f"View {view_id} not found",
        }, status_code=404)

    # Execute the view's SQL query
    db = get_db_manager()
    error = None
    rows = []
    columns = []

    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(view['sql'])
            rows = cursor.fetchall()
            if rows:
                columns = [desc[0] for desc in cursor.description]
    except Exception as e:
        error = str(e)

    sidebar_views = get_views_for_sidebar()

    return templates.TemplateResponse("views/show.html", {
        "request": request,
        "view": view,
        "rows": rows,
        "columns": columns,
        "error": error,
        "sidebar_views": sidebar_views,
        "current_view_id": view_id,
    })


@router.get("/{view_id}/content", response_class=HTMLResponse)
async def view_content(request: Request, view_id: int):
    """Get view content for HTMX partial update."""
    view = get_view(view_id)

    if not view:
        return HTMLResponse(
            content="<div class='alert alert-error'>View not found</div>",
            status_code=404
        )

    # Execute the view's SQL query
    db = get_db_manager()
    error = None
    rows = []
    columns = []

    try:
        with db.get_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(view['sql'])
            rows = cursor.fetchall()
            if rows:
                columns = [desc[0] for desc in cursor.description]
    except Exception as e:
        error = str(e)

    # Return partial template for HTMX
    return templates.TemplateResponse("partials/view_content.html", {
        "request": request,
        "view": view,
        "rows": rows,
        "columns": columns,
        "error": error,
    })
