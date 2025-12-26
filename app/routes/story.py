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
