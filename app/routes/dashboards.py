"""Dashboard routes."""
from typing import Optional
import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dashboards import (
    get_all_dashboards, get_dashboard, create_dashboard,
    update_dashboard, delete_dashboard, get_default_dashboard_config,
    get_saved_views, create_view, delete_view,
)
from app.introspection import get_all_tables, introspect_table
from app.database import get_db_manager

router = APIRouter(prefix="/dashboards")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def list_dashboards(request: Request):
    """List all dashboards."""
    dashboards = get_all_dashboards()
    views = get_saved_views()

    return templates.TemplateResponse("dashboards/list.html", {
        "request": request,
        "dashboards": dashboards,
        "views": views,
    })


@router.get("/default", response_class=HTMLResponse)
async def default_dashboard(request: Request):
    """Show auto-generated default dashboard."""
    tables = get_all_tables()
    table_summaries = []

    for table_name in tables:
        info = introspect_table(table_name)
        table_summaries.append({
            'name': table_name,
            'row_count': info.row_count,
            'column_count': len(info.columns),
            'columns': [c.name for c in info.columns[:5]],  # First 5 columns
        })

    db = get_db_manager()

    return templates.TemplateResponse("dashboards/default.html", {
        "request": request,
        "tables": table_summaries,
        "db_name": db.target_db_name,
        "multiple_dbs": db.multiple_dbs_detected,
        "available_dbs": db.available_dbs,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_dashboard_form(request: Request):
    """Render form for creating a new dashboard."""
    tables = get_all_tables()

    return templates.TemplateResponse("dashboards/form.html", {
        "request": request,
        "mode": "create",
        "dashboard": None,
        "tables": tables,
    })


@router.post("/new")
async def create_new_dashboard(
    request: Request,
    name: str = Form(...),
):
    """Create a new dashboard."""
    form_data = await request.form()

    # Build config from selected tables
    selected_tables = form_data.getlist("tables")
    config = {
        'layout': 'grid',
        'widgets': [
            {
                'type': 'table_summary',
                'table': table,
            }
            for table in selected_tables
        ]
    }

    dashboard_id = create_dashboard(name, config)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/dashboards/{dashboard_id}"}
        )

    return RedirectResponse(url=f"/dashboards/{dashboard_id}", status_code=303)


@router.get("/{dashboard_id}", response_class=HTMLResponse)
async def view_dashboard(request: Request, dashboard_id: int):
    """View a specific dashboard."""
    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return templates.TemplateResponse("errors/404.html", {
            "request": request,
            "message": f"Dashboard {dashboard_id} not found",
        }, status_code=404)

    # Fetch data for widgets
    widgets_data = []
    for widget in dashboard.config.get('widgets', []):
        if widget.get('type') == 'table_summary':
            table_name = widget.get('table')
            try:
                info = introspect_table(table_name)
                widgets_data.append({
                    **widget,
                    'row_count': info.row_count,
                    'column_count': len(info.columns),
                    'columns': [c.name for c in info.columns[:5]],
                })
            except Exception:
                widgets_data.append({
                    **widget,
                    'error': f"Table '{table_name}' not found",
                })
        else:
            widgets_data.append(widget)

    return templates.TemplateResponse("dashboards/view.html", {
        "request": request,
        "dashboard": dashboard,
        "widgets": widgets_data,
    })


@router.get("/{dashboard_id}/edit", response_class=HTMLResponse)
async def edit_dashboard_form(request: Request, dashboard_id: int):
    """Render form for editing a dashboard."""
    dashboard = get_dashboard(dashboard_id)

    if not dashboard:
        return templates.TemplateResponse("errors/404.html", {
            "request": request,
            "message": f"Dashboard {dashboard_id} not found",
        }, status_code=404)

    tables = get_all_tables()
    selected_tables = [
        w.get('table') for w in dashboard.config.get('widgets', [])
        if w.get('type') == 'table_summary'
    ]

    return templates.TemplateResponse("dashboards/form.html", {
        "request": request,
        "mode": "edit",
        "dashboard": dashboard,
        "tables": tables,
        "selected_tables": selected_tables,
    })


@router.post("/{dashboard_id}/edit")
async def update_existing_dashboard(
    request: Request,
    dashboard_id: int,
    name: str = Form(...),
):
    """Update a dashboard."""
    form_data = await request.form()

    selected_tables = form_data.getlist("tables")
    config = {
        'layout': 'grid',
        'widgets': [
            {
                'type': 'table_summary',
                'table': table,
            }
            for table in selected_tables
        ]
    }

    update_dashboard(dashboard_id, name=name, config=config)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": f"/dashboards/{dashboard_id}"}
        )

    return RedirectResponse(url=f"/dashboards/{dashboard_id}", status_code=303)


@router.delete("/{dashboard_id}")
async def delete_existing_dashboard(request: Request, dashboard_id: int):
    """Delete a dashboard."""
    delete_dashboard(dashboard_id)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/dashboards"}
        )

    return RedirectResponse(url="/dashboards", status_code=303)


# Views routes

@router.get("/views/new", response_class=HTMLResponse)
async def new_view_form(request: Request):
    """Render form for creating a new saved view."""
    tables = get_all_tables()

    return templates.TemplateResponse("dashboards/view_form.html", {
        "request": request,
        "tables": tables,
    })


@router.post("/views/new")
async def create_new_view(
    request: Request,
    name: str = Form(...),
    sql: str = Form(...),
    source_table: Optional[str] = Form(None),
):
    """Create a new saved view."""
    view_id = create_view(name, sql, source_table)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/dashboards"}
        )

    return RedirectResponse(url="/dashboards", status_code=303)


@router.delete("/views/{view_id}")
async def delete_existing_view(request: Request, view_id: int):
    """Delete a saved view."""
    delete_view(view_id)

    if request.headers.get("HX-Request"):
        return HTMLResponse(content="")

    return RedirectResponse(url="/dashboards", status_code=303)
