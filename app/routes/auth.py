"""Authentication routes."""
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import authenticate, create_session, validate_session
from app.config import SESSION_COOKIE_NAME

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
    })


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission."""
    user = authenticate(username, password)

    if user:
        token = create_session(user)
        redirect = RedirectResponse(url="/", status_code=303)
        redirect.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
        )
        return redirect

    # Return error with HTMX partial if it's an HTMX request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/login_form.html",
            {
                "request": request,
                "error": "Invalid username or password",
                "username": username,
            },
            status_code=401,
        )

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Invalid username or password",
            "username": username,
        },
        status_code=401,
    )


@router.get("/logout")
async def logout():
    """Handle logout."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
