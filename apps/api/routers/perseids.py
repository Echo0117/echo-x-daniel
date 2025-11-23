from pathlib import Path
from datetime import date
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---- personalize here (mirrors your PyWebIO constants) ----
MEETING_DATE   = date(2025, 6, 23)
DATE_NIGHT     = date(2025, 8, 12)
BOYFRIEND_NAME = "Honey"
YOUR_NAME      = "Your favorite Echo"
RESTAURANT     = "Dinner for Two"
FERRIS         = "Ferris Wheel Adventure"
OCEAN          = "Ocean View Point"
AUDIO_SRC      = "/static/brooklyn_baby.mp3"  # or external URL

def days_since(d: date) -> int:
    return (date.today() - d).days

@router.get("/perseids", response_class=HTMLResponse)
async def perseids(request: Request):
    ctx = {
        "request": request,
        "meeting_days": days_since(MEETING_DATE),
        "meeting_date": MEETING_DATE.strftime("%b %d, %Y"),
        "date_night": DATE_NIGHT.strftime("%b %d"),
        "boyfriend": BOYFRIEND_NAME,
        "yourname": YOUR_NAME,
        "restaurant": RESTAURANT,
        "ferris": FERRIS,
        "ocean": OCEAN,
        "audio_src": AUDIO_SRC,
        # the little notes you revealed one-by-one
        "notes": [
            "You feel like home.",
            "I love the way you say my name.",
            "Thank you for being gentle with my heart.",
            "I’m proud of you — always.",
            "You make ordinary days sparkle.",
            "You’re my favorite “what are you doing?”",
            "I can’t wait for our ferris wheel wish.",
            "Under the Perseids, it’s you + me.",
        ],
    }
    return templates.TemplateResponse("perseids.html", ctx)
