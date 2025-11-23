from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["eighteen-days"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/eighteen-days", response_class=HTMLResponse)
def eighteen_days(request: Request):
    return templates.TemplateResponse(
        "eighteen_days.html",
        {"request": request}
    )
