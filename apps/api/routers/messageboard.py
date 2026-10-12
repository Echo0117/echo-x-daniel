# routers/messageboard.py
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from typing import List
from datetime import date
from pathlib import Path

from services.messageboard import (
    require_auth, check_login,
    save_message, list_messages,
    MessageIn, MessageOut, SESSION_USER_KEY, export_csv
)

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("messageboard_form.html", {"request": request, "mode": "login"})

@router.post("/login")
async def login_action(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/messageboard")):
    if not check_login(username, password):
        return templates.TemplateResponse("messageboard_form.html", {"request": request, "mode": "login", "error": "Invalid credentials"})
    request.session[SESSION_USER_KEY] = username
    return RedirectResponse(url=next, status_code=303)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/messageboard", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def messageboard_form(request: Request):
    return templates.TemplateResponse("messageboard_form.html", {"request": request, "mode": "write"})

@router.get("/messageboard-wall", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def messageboard_wall(request: Request):
    items = [m.model_dump() for m in list_messages(limit=50)]
    return templates.TemplateResponse("messageboard_wall.html", {"request": request, "items": items})

@router.post("/api/messages", response_model=MessageOut, dependencies=[Depends(require_auth)])
async def create_message(msg: MessageIn, request: Request):
    if not msg.author.strip() or not msg.content.strip():
        raise HTTPException(status_code=400, detail="author and content are required")
    return save_message(msg, request)

@router.get("/api/messages", response_model=List[MessageOut], dependencies=[Depends(require_auth)])
async def get_messages(limit: int = 20):
    return list_messages(limit=limit)

def _csv_download(text: str, name: str) -> Response:
    # BOM so Excel opens UTF-8 (emoji, Chinese) correctly
    filename = f"{name}-{date.today().isoformat()}.csv"
    return Response(
        content="\ufeff" + text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/messageboard.csv", dependencies=[Depends(require_auth)])
async def export_messages():
    return _csv_download(export_csv(), "messageboard")
