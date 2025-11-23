from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["three-weeks"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/three-weeks", response_class=HTMLResponse)
def three_weeks(request: Request):
    return templates.TemplateResponse(
        "three_weeks.html",
        {"request": request}
    )
