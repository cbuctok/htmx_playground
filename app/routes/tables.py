"""Table CRUD routes."""
from typing import Optional
from fastapi import APIRouter, Request, Form, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.introspection import get_all_tables, introspect_table
from app.semantics import get_table_semantics
from app.crud import (
    list_rows, get_row, create_row, update_row, delete_row,
    get_form_fields, get_pk_column,
)
from app.branding import get_ui_preferences
from app.auth import User
from app.dashboards import get_views_for_sidebar

router = APIRouter(prefix="/tables")
templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request) -> Optional[User]:
    """Get current user from request state."""
    return getattr(request.state, 'user', None)


@router.get("", response_class=HTMLResponse)
async def list_tables(request: Request):
    """List all tables in the target database."""
    tables = get_all_tables()
    table_info = []

    for table_name in tables:
        info = introspect_table(table_name)
        table_info.append({
            'name': table_name,
            'row_count': info.row_count,
            'column_count': len(info.columns),
        })

    sidebar_views = get_views_for_sidebar()

    return templates.TemplateResponse("tables/list.html", {
        "request": request,
        "tables": table_info,
        "sidebar_views": sidebar_views,
    })


@router.get("/{table_name}", response_class=HTMLResponse)
async def view_table(
    request: Request,
    table_name: str,
    page: int = Query(1, ge=1),
    sort: Optional[str] = None,
    order: str = Query("asc", regex="^(asc|desc)$"),
    search: Optional[str] = None,
):
    """View table rows with pagination and sorting."""
    prefs = get_ui_preferences()
    table_info = introspect_table(table_name)
    semantics = get_table_semantics(table_name)

    rows, total_count = list_rows(
        table_name,
        page=page,
        page_size=prefs.page_size,
        sort_column=sort,
        sort_order=order,
        search=search,
    )

    total_pages = (total_count + prefs.page_size - 1) // prefs.page_size
    pk_column = get_pk_column(table_name)

    sidebar_views = get_views_for_sidebar()

    context = {
        "request": request,
        "table_name": table_name,
        "table_info": table_info,
        "columns": table_info.columns,
        "rows": rows,
        "semantics": semantics,
        "pk_column": pk_column,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "sort": sort,
        "order": order,
        "search": search or "",
        "sidebar_views": sidebar_views,
    }

    # Return partial for HTMX requests
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/table_rows.html", context)

    return templates.TemplateResponse("tables/view.html", context)


@router.get("/{table_name}/new", response_class=HTMLResponse)
async def new_row_form(request: Request, table_name: str):
    """Render form for creating a new row."""
    fields = get_form_fields(table_name, mode='create')

    return templates.TemplateResponse("tables/form.html", {
        "request": request,
        "table_name": table_name,
        "fields": fields,
        "mode": "create",
        "row": None,
    })


@router.post("/{table_name}/new")
async def create_new_row(request: Request, table_name: str):
    """Create a new row."""
    form_data = await request.form()
    user = get_current_user(request)

    data = {}
    for key, value in form_data.items():
        if value:  # Only include non-empty values
            data[key] = value

    try:
        row_id = create_row(table_name, data, current_user=user.username if user else None)

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content="",
                headers={"HX-Redirect": f"/tables/{table_name}"}
            )

        return RedirectResponse(url=f"/tables/{table_name}", status_code=303)

    except Exception as e:
        fields = get_form_fields(table_name, mode='create')
        return templates.TemplateResponse("tables/form.html", {
            "request": request,
            "table_name": table_name,
            "fields": fields,
            "mode": "create",
            "row": data,
            "error": str(e),
        }, status_code=400)


@router.get("/{table_name}/{pk_value}/edit", response_class=HTMLResponse)
async def edit_row_form(request: Request, table_name: str, pk_value: str):
    """Render form for editing a row."""
    row = get_row(table_name, pk_value)

    if not row:
        return templates.TemplateResponse("errors/404.html", {
            "request": request,
            "message": f"Row with ID {pk_value} not found",
        }, status_code=404)

    fields = get_form_fields(table_name, mode='edit')

    return templates.TemplateResponse("tables/form.html", {
        "request": request,
        "table_name": table_name,
        "fields": fields,
        "mode": "edit",
        "row": row,
        "pk_value": pk_value,
    })


@router.post("/{table_name}/{pk_value}/edit")
async def update_existing_row(request: Request, table_name: str, pk_value: str):
    """Update an existing row."""
    form_data = await request.form()
    user = get_current_user(request)

    data = {}
    for key, value in form_data.items():
        data[key] = value if value else None

    try:
        update_row(table_name, pk_value, data, current_user=user.username if user else None)

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content="",
                headers={"HX-Redirect": f"/tables/{table_name}"}
            )

        return RedirectResponse(url=f"/tables/{table_name}", status_code=303)

    except Exception as e:
        fields = get_form_fields(table_name, mode='edit')
        row = get_row(table_name, pk_value)
        return templates.TemplateResponse("tables/form.html", {
            "request": request,
            "table_name": table_name,
            "fields": fields,
            "mode": "edit",
            "row": row,
            "pk_value": pk_value,
            "error": str(e),
        }, status_code=400)


@router.delete("/{table_name}/{pk_value}")
async def delete_existing_row(request: Request, table_name: str, pk_value: str):
    """Delete a row."""
    user = get_current_user(request)
    deleted = delete_row(table_name, pk_value, current_user=user.username if user else None)

    if request.headers.get("HX-Request"):
        if deleted:
            # Return empty to remove the row from DOM
            return HTMLResponse(content="")
        return HTMLResponse(content="Row not found", status_code=404)

    return RedirectResponse(url=f"/tables/{table_name}", status_code=303)


@router.get("/{table_name}/schema", response_class=HTMLResponse)
async def view_table_schema(request: Request, table_name: str):
    """View table schema details."""
    table_info = introspect_table(table_name)
    semantics = get_table_semantics(table_name)
    sidebar_views = get_views_for_sidebar()

    return templates.TemplateResponse("tables/schema.html", {
        "request": request,
        "table_name": table_name,
        "table_info": table_info,
        "columns": table_info.columns,
        "foreign_keys": table_info.foreign_keys,
        "semantics": semantics,
        "sidebar_views": sidebar_views,
    })
