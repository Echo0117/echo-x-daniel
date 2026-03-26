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
POEMS_ROOT = ROOT / "poems"
MINE_DIR   = POEMS_ROOT / "mine"
DANIEL_DIR = POEMS_ROOT / "daniel"
FOUND_DIR  = POEMS_ROOT / "found"
for d in (MINE_DIR, DANIEL_DIR, FOUND_DIR): d.mkdir(parents=True, exist_ok=True)

PATTERNS = ("*.md","*.markdown","*.MD","*.MARKDOWN")

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _split(md: str):
    import re
    lines = md.splitlines()
    title = author = date_s = None
    drop = set()
    for i,ln in enumerate(lines):
        m = re.match(r'^\s*#\s+(.+?)\s*$', ln)
        if m: title=m.group(1).strip(); drop.add(i); break
    for i,ln in enumerate(lines):
        m = re.match(r'^\s*_author:\s*(.+?)\s*_\s*$', ln, flags=re.I)
        if m: author=m.group(1).strip(); drop.add(i); break
    for i,ln in enumerate(lines):
        m = re.match(r'^\s*_date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*_\s*$', ln, flags=re.I)
        if m: date_s=m.group(1).strip(); drop.add(i); break
    body = "\n".join(ln for i,ln in enumerate(lines) if i not in drop).strip()
    return dict(title=title, author=author, date=date_s, body=body)

def _parse(path: Path, kind: str) -> Dict:
    slug = path.stem
    parts = _split(_read(path))
    if "_" in slug:
        maybe_date, rest = slug.split("_",1)
        title_guess = rest.replace("-"," ").title()
        try: date_from_name = datetime.strptime(maybe_date, "%Y-%m-%d").date()
        except: date_from_name = None
    else:
        title_guess = slug.replace("-"," ").title(); date_from_name=None
    title = parts["title"] or title_guess
    date = None
    if parts["date"]:
        try: date = datetime.strptime(parts["date"], "%Y-%m-%d").date()
        except: pass
    if not date and date_from_name: date = date_from_name
    return dict(kind=kind, slug=slug, title=title, author=parts["author"], date=date, body_md=parts["body"])

def _list(folder: Path, kind: str) -> List[Dict]:
    files = []
    for pat in PATTERNS:
        files += list(folder.glob(pat))
    items = [_parse(p, kind) for p in files]
    items.sort(key=lambda x:(x["date"] or datetime.min.date(), x["slug"]), reverse=True)
    return items

def _folder(kind: str) -> Path:
    if kind == "mine": return MINE_DIR
    if kind == "daniel": return DANIEL_DIR
    return FOUND_DIR

@router.get("/", response_class=HTMLResponse)
def poetry_index(request: Request, kind: str = "mine"):
    folder = _folder(kind)
    items = _list(folder, kind)
    return templates.TemplateResponse("poetry_list.html", {"request": request, "kind": kind, "items": items})

@router.get("/open/{kind}/{slug}", response_class=HTMLResponse)
def poetry_open(request: Request, kind: str, slug: str):
    folder = _folder(kind)
    items = _list(folder, kind)
    it = next((x for x in items if x["slug"]==slug), None)
    if not it: return HTMLResponse("Not found", status_code=404)

    # light markdown → paragraphs
    safe = html.escape(it["body_md"]).splitlines()
    paras=[]; buf=[]
    for ln in safe:
        if not ln.strip():
            if buf: paras.append("<p>"+"<br>".join(buf)+"</p>"); buf=[]
        else: buf.append(ln)
    if buf: paras.append("<p>"+"<br>".join(buf)+"</p>")

    return templates.TemplateResponse("poetry_detail.html", {
        "request": request,
        "kind": kind,
        "title": it["title"],
        "author": "Echo" if kind=="mine" else ("Daniel" if kind=="daniel" else (it["author"] or "—")),
        "date": it["date"].strftime("%Y-%m-%d") if it["date"] else "—",
        "body_html": "".join(paras)
    })