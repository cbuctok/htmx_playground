"""Story Mode routes for guided data entry and admin management."""
from typing import Optional
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.story import (
    get_story_steps,
    get_story_step,
    update_story_step,
    reorder_story_steps,
    regenerate_story_steps,
    is_story_mode_enabled,
    set_story_mode_enabled,
    get_story_progress,
    get_current_story_step,
    get_step_progress,
    get_table_dependencies_display,
    build_dependency_graph,
    cache_dependency_graph,
    # Demo/Play mode functions
    play_story_step,
    play_all_story_steps,
    get_demo_preview,
    clear_demo_data,
    clear_all_demo_data,
)
from app.branding import get_app_config, get_ui_preferences
from app.database import get_db_manager

router = APIRouter(prefix="/story")
templates = Jinja2Templates(directory="templates")


def get_template_context(request: Request) -> dict:
    """Build common template context."""
    db = get_db_manager()
    return {
        "request": request,
        "user": getattr(request.state, 'user', None),
        "config": get_app_config(),
        "prefs": get_ui_preferences(),
        "db_name": db.target_db_name,
        "multiple_dbs": db.multiple_dbs_detected,
    }


def require_admin(request: Request) -> bool:
    """Check if current user is admin."""
    user = getattr(request.state, 'user', None)
    return user is not None and user.is_admin


# User-facing Story Mode routes

@router.get("", response_class=HTMLResponse)
async def story_mode(request: Request):
    """
    Main Story Mode view.

    Shows guided data entry flow with progress tracking.
    """
    context = get_template_context(request)

    story_enabled = is_story_mode_enabled()
    if not story_enabled:
        # Show message that Story Mode is disabled
        context['story_enabled'] = False
        return templates.TemplateResponse("story/disabled.html", context)

    progress = get_story_progress()
    current_step = get_current_story_step()

    context.update({
        'story_enabled': True,
        'progress': progress,
        'current_step': current_step,
    })

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/story_progress.html", context)

    return templates.TemplateResponse("story/index.html", context)


@router.get("/step/{step_id}", response_class=HTMLResponse)
async def view_step(request: Request, step_id: int):
    """View a specific story step."""
    context = get_template_context(request)

    step = get_story_step(step_id)
    if not step:
        return templates.TemplateResponse("errors/404.html", {
            **context,
            "message": f"Story step {step_id} not found",
        }, status_code=404)

    progress = get_step_progress(step)
    dependencies = get_table_dependencies_display(step.source_name)

    # Get all steps for navigation
    all_steps = get_story_steps(include_disabled=False)
    current_index = next(
        (i for i, s in enumerate(all_steps) if s.id == step_id),
        None
    )

    prev_step = all_steps[current_index - 1] if current_index and current_index > 0 else None
    next_step = all_steps[current_index + 1] if current_index is not None and current_index < len(all_steps) - 1 else None

    context.update({
        'step': step,
        'progress': progress,
        'dependencies': dependencies,
        'prev_step': prev_step,
        'next_step': next_step,
        'step_number': current_index + 1 if current_index is not None else 1,
        'total_steps': len(all_steps),
    })

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/story_step.html", context)

    return templates.TemplateResponse("story/step.html", context)


# Admin Story Management routes

@router.get("/admin", response_class=HTMLResponse)
async def admin_story(request: Request):
    """Admin view for Story Mode management."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    context = get_template_context(request)

    story_enabled = is_story_mode_enabled()
    steps = get_story_steps(include_disabled=True)
    graph = build_dependency_graph()

    # Add progress info to each step
    steps_with_progress = []
    for step in steps:
        progress = get_step_progress(step)
        steps_with_progress.append({
            'step': step,
            'progress': progress,
        })

    context.update({
        'story_enabled': story_enabled,
        'steps': steps_with_progress,
        'graph': graph,
    })

    return templates.TemplateResponse("admin/story.html", context)


@router.post("/admin/toggle", response_class=HTMLResponse)
async def toggle_story_mode(request: Request, enabled: str = Form(...)):
    """Enable or disable Story Mode."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    set_story_mode_enabled(enabled.lower() == 'true')

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/story/admin"}
        )

    return RedirectResponse(url="/story/admin", status_code=303)


@router.get("/admin/step/{step_id}/edit", response_class=HTMLResponse)
async def edit_step_form(request: Request, step_id: int):
    """Form to edit a story step."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    context = get_template_context(request)

    step = get_story_step(step_id)
    if not step:
        return templates.TemplateResponse("errors/404.html", {
            **context,
            "message": f"Story step {step_id} not found",
        }, status_code=404)

    context['step'] = step

    return templates.TemplateResponse("admin/story_step_form.html", context)


@router.post("/admin/step/{step_id}/edit")
async def edit_step(
    request: Request,
    step_id: int,
    title: str = Form(...),
    description: str = Form(""),
    min_records_required: int = Form(1),
    enabled: str = Form("false"),
):
    """Update a story step."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    update_story_step(
        step_id=step_id,
        title=title,
        description=description,
        min_records_required=min_records_required,
        enabled=enabled.lower() == 'true',
    )

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/story/admin"}
        )

    return RedirectResponse(url="/story/admin", status_code=303)


@router.post("/admin/reorder")
async def reorder_steps(request: Request):
    """
    Reorder story steps.

    Expects form data with step_ids[] array in desired order.
    """
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    form_data = await request.form()
    step_ids = form_data.getlist('step_ids[]')

    if step_ids:
        reorder_story_steps([int(sid) for sid in step_ids])

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="alert alert-success">Steps reordered successfully</div>'
        )

    return RedirectResponse(url="/story/admin", status_code=303)


@router.post("/admin/regenerate")
async def regenerate_story(request: Request):
    """Regenerate story steps from current schema."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    cache_dependency_graph()
    regenerate_story_steps()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content="",
            headers={"HX-Redirect": "/story/admin"}
        )

    return RedirectResponse(url="/story/admin", status_code=303)


@router.get("/admin/graph", response_class=HTMLResponse)
async def view_dependency_graph(request: Request):
    """View the dependency graph visualization."""
    if not require_admin(request):
        return RedirectResponse(url="/", status_code=303)

    context = get_template_context(request)

    graph = build_dependency_graph()

    context['graph'] = graph

    return templates.TemplateResponse("admin/dependency_graph.html", context)


# =============================================================================
# Demo/Play Mode routes
# =============================================================================

@router.get("/play", response_class=HTMLResponse)
async def play_mode(request: Request):
    """
    Demo/Play Mode view.

    Shows the story with play controls for auto-generating demo data.
    """
    context = get_template_context(request)

    progress = get_story_progress()
    steps = get_story_steps(include_disabled=False)

    # Add progress and preview to each step
    steps_with_info = []
    for step in steps:
        step_progress = get_step_progress(step)
        preview = get_demo_preview(step.source_name, num_samples=1)
        steps_with_info.append({
            'step': step,
            'progress': step_progress,
            'preview': preview[0] if preview else {},
        })

    context.update({
        'progress': progress,
        'steps': steps_with_info,
    })

    return templates.TemplateResponse("story/play.html", context)


@router.post("/play/step/{step_id}")
async def play_step(
    request: Request,
    step_id: int,
    num_records: int = Form(1),
):
    """
    Play a single story step by inserting demo data.

    Returns the result of the operation.
    """
    step = get_story_step(step_id)
    if not step:
        return HTMLResponse(
            content='<div class="alert alert-error">Step not found</div>',
            status_code=404
        )

    result = play_story_step(step, num_records)

    if request.headers.get("HX-Request"):
        if result['success']:
            # Return updated step progress
            progress = get_step_progress(step)
            return templates.TemplateResponse("partials/play_step_result.html", {
                "request": request,
                "step": step,
                "result": result,
                "progress": progress,
            })
        else:
            return HTMLResponse(
                content=f'<div class="alert alert-error">Failed: {result.get("errors", "Unknown error")}</div>'
            )

    return RedirectResponse(url="/story/play", status_code=303)


@router.post("/play/all")
async def play_all_steps(
    request: Request,
    records_per_step: int = Form(1),
):
    """
    Play all story steps sequentially.

    Inserts demo data for each step in order.
    """
    results = play_all_story_steps(records_per_step)

    if request.headers.get("HX-Request"):
        progress = get_story_progress()
        return templates.TemplateResponse("partials/play_all_result.html", {
            "request": request,
            "results": results,
            "progress": progress,
        })

    return RedirectResponse(url="/story/play", status_code=303)


@router.post("/play/clear/{table_name}")
async def clear_table_data(request: Request, table_name: str):
    """Clear all data from a specific table."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    count = clear_demo_data(table_name)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content=f'<div class="alert alert-success">Cleared {count} rows from {table_name}</div>'
        )

    return RedirectResponse(url="/story/play", status_code=303)


@router.post("/play/clear-all")
async def clear_all_data(request: Request):
    """Clear all data from all tables."""
    if not require_admin(request):
        return HTMLResponse(content="Unauthorized", status_code=403)

    results = clear_all_demo_data()
    total = sum(results.values())

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content=f'<div class="alert alert-success">Cleared {total} rows from {len(results)} tables</div>',
            headers={"HX-Redirect": "/story/play"}
        )

    return RedirectResponse(url="/story/play", status_code=303)


@router.get("/play/preview/{table_name}", response_class=HTMLResponse)
async def preview_demo_data(request: Request, table_name: str):
    """
    Preview what demo data would look like for a table.
    """
    context = get_template_context(request)

    preview = get_demo_preview(table_name, num_samples=5)

    context.update({
        'table_name': table_name,
        'preview': preview,
    })

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/demo_preview.html", context)

    return templates.TemplateResponse("story/preview.html", context)
