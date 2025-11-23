from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/two-weeks", response_class=HTMLResponse)
async def two_weeks_v1_get(request: Request):
    return templates.TemplateResponse("two_weeks_v1.html", {"request": request, "name": None, "mood": None, "gif": None})

@router.post("/two-weeks", response_class=HTMLResponse)
async def two_weeks_v1_post(request: Request, name: str = Form(""), mood: str = Form("")):
    msg = {
        "happy": "Your happiness lights up my world! 💛",
        "sad": "I'm here to cheer you up! 🍀",
        "excited": "Your excitement is contagious! 🎉",
    }.get(mood or "", "You are my sunshine ✨")
    return templates.TemplateResponse("two_weeks_v1.html", {"request": request, "name": name, "mood": msg, "gif": True})

@router.get("/two-weeks2", response_class=HTMLResponse)
async def two_weeks_menu_get(request: Request):
    return templates.TemplateResponse("two_weeks_menu.html", {"request": request, "step": "menu"})

@router.post("/two-weeks2", response_class=HTMLResponse)
async def two_weeks_menu_post(request: Request, action: str = Form(""), nickname: str = Form(""), mood: str = Form("")):
    ctx = {"request": request, "step": "menu"}
    if action == "nickname":
        ctx.update({"step": "nickname", "nickname": nickname})
    elif action == "day":
        msg = {
            "great":"So glad you had a great day! You deserve all the smiles. 😁",
            "bad":"I'm sorry you had a bad day. I’m here whenever you need me. 🤗",
            "amazing":"Your amazing days light up my world! ✨",
        }.get(mood or "", "I’m here with you, always 💞")
        ctx.update({"step": "day", "mood_msg": msg})
    elif action == "surprise":
        ctx.update({"step": "surprise"})
    return templates.TemplateResponse("two_weeks_menu.html", ctx)

@router.get("/first-love", response_class=HTMLResponse, name="first_love")
def first_love_get(request: Request):
    gif_url = request.url_for("static", path="img/kiss.gif")
    return templates.TemplateResponse(
        "first_love.html",
        {"request": request, "result": None, "gif_url": gif_url, "preview_img": None},
    )


@router.post("/first-love", response_class=HTMLResponse)
async def first_love_post(request: Request, text: str = Form("")):
    # lightweight faux analysis to preserve logic without heavy ML
    themes = [
        ("Destiny", 0.92), ("Unspoken Love", 0.88), ("Serendipity", 0.90),
        ("Shared Dreams", 0.87), ("Forever Promises", 0.89),
    ]
    import random
    theme, score = random.choice(themes)
    result = {
        "theme": theme,
        "score": f"{score:.0%}",
        "compliment": random.choice([
            "Your smile is my favorite sunrise 🌅",
            "You're the poetry my soul always sought 💖",
            "Even time slows when you hold my hand ⏳",
        ]),
    }
    return templates.TemplateResponse("first_love.html", {"request": request, "result": result, "preview": None})