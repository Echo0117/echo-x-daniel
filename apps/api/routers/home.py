from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    view = request.query_params.get("view", "modern").strip().lower()
    template_name = "home_classic.html" if view == "classic" else "home_modern.html"
    return templates.TemplateResponse(template_name, {"request": request, "home_view": view})
