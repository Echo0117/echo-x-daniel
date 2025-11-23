import os, glob, html
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("APP_ROOT", str(APP_ROOT)))
LETTERS_DIR = Path(os.getenv("LETTERS_DIR", str(ROOT / "letters")))
LETTERS_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS = ("*.md","*.markdown","*.MD","*.MARKDOWN")

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _iter_paths() -> List[Path]:
    files: List[Path] = []
    for pat in PATTERNS:
        files += list(LETTERS_DIR.glob(pat))
    # de-dup
    seen, uniq = set(), []
    for f in files:
        if str(f) not in seen:
            seen.add(str(f)); uniq.append(f)
    return uniq

def _parse(path: Path) -> Dict:
    slug = path.stem
    if "_" in slug:
        date_part, title_part = slug.split("_", 1)
        list_title = title_part.replace("-"," ").title()
    else:
        date_part, list_title = None, slug.replace("-"," ").title()
    date = None
    if date_part:
        try: date = datetime.strptime(date_part, "%Y-%m-%d").date()
        except: pass
    return dict(slug=slug, list_title=list_title, date=date, body_md=_read(path))

@router.get("/", response_class=HTMLResponse)
def list_letters(request: Request):
    items = [_parse(p) for p in _iter_paths()]
    items.sort(key=lambda x:(x["date"] or datetime.min.date(), x["slug"]), reverse=True)
    return templates.TemplateResponse("letters_list.html", {"request": request, "items": items, "letters_dir": str(LETTERS_DIR)})

@router.get("/open/{slug}", response_class=HTMLResponse)
def open_letter(request: Request, slug: str):
    for p in _iter_paths():
        if p.stem == slug:
            it = _parse(p)
            # markdown → html (best effort, optional dependency)
            body_html = None
            try:
                import markdown as md
                body_html = md.markdown(it["body_md"], extensions=["extra"])  # type: ignore
            except Exception:
                esc = html.escape(it["body_md"]).replace("\n\n","</p><p>").replace("\n","<br/>")
                body_html = f"<p>{esc}</p>"
            return templates.TemplateResponse("letter_detail.html", {
                "request": request,
                "title": "Love You",
                "date": it["date"].strftime("%Y-%m-%d") if it["date"] else "—",
                "body_html": body_html
            })
    return HTMLResponse("Not found", status_code=404)