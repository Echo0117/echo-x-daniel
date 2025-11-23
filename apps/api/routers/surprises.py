# routers/surprises.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["surprises"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------- /two-weeks/menu : 3-step flow ----------------

@router.get("/two-weeks/menu", response_class=HTMLResponse, name="two_weeks_menu")
def two_weeks_menu_get(request: Request):
    # Start at step 1
    return templates.TemplateResponse(
        "two_weeks_menu.html",
        {"request": request, "step": 1, "context": {}},
    )

@router.post("/two-weeks/menu", response_class=HTMLResponse)
def two_weeks_menu_post(
    request: Request,
    step: int = Form(...),
    his_nick: str | None = Form(None),
    mood: str | None = Form(None),
    sub: str | None = Form(None),
):
    ctx = {}
    next_step = step

    if step == 1 and his_nick:
        ctx["line"] = f"Aww, you call me “{his_nick}” — it melts my heart! ❤️"
        next_step = 2

    elif step == 2 and mood:
        if mood == "great":
            ctx["line"] = "So glad you had a great day! You deserve all the smiles. 😁"
        elif mood == "bad":
            ctx["line"] = "I'm sorry today was rough. I’m here whenever you need me. 🤗"
        else:
            ctx["line"] = "Your amazing days light up my world! ✨"
        next_step = 3

    elif step == 3 and sub:
        if sub == "photo":
            ctx["html"] = "<h3>A picture of a cutie pie 🥰</h3>"
            ctx["img"] = "/static/img/miss_you_compressed.JPG"
        elif sub == "gif":
            ctx["html"] = "<h3>Enjoy this vibe! 🎉</h3>"
            ctx["img"] = "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif"
        else:
            ctx["html"] = "<h3>Your secret message 💌</h3>"
            ctx["line"] = "“I’m grateful every day — thank you for finding me.”"
        next_step = 4  # done

    # If the request is HTMX, return only the inner fragment (no full page reload)
    if request.headers.get("Hx-Request") == "true":
        return templates.TemplateResponse(
            "partials/tw_menu_step.html",
            {"request": request, "step": next_step, "context": ctx},
        )

    # Fallback: render whole page
    return templates.TemplateResponse(
        "two_weeks_menu.html",
        {"request": request, "step": next_step, "context": ctx},
    )


# ---------------- /two-weeks/v1 : 4-step flow ----------------
@router.get("/two-weeks/v1", response_class=HTMLResponse, name="two_weeks_v1")
def two_weeks_v1_get(request: Request):
    return templates.TemplateResponse(
        "two_weeks_v1.html",
        {"request": request, "step": 1, "context": {}},
    )

@router.post("/two-weeks/v1", response_class=HTMLResponse)
def two_weeks_v1_post(
    request: Request,
    step: int = Form(...),
    name: str | None = Form(None),
    mood: str | None = Form(None),
    cont: str | None = Form(None),
    more: str | None = Form(None),
):
    ctx = {}
    next_step = step

    if step == 1 and name:
        ctx["title"] = f"Happy Two Weeks, {name}! 💖"
        ctx["line"] = "You make everything softer and brighter."
        next_step = 2

    elif step == 2 and mood:
        if mood == "happy":
            ctx["line"] = "Your happiness lights up my world! 💛"
        elif mood == "sad":
            ctx["line"] = "I’m here to cheer you up, always. 🍀"
        else:
            ctx["line"] = "Your excitement is contagious! 🎉"
        next_step = 3

    elif step == 3 and cont:
        if cont == "yes":
            ctx["html"] = "<h3 style='margin:0;'>🎁 A tiny surprise 🎁</h3>"
            ctx["img"] = "https://media.giphy.com/media/xT0BKmtQGLbumr5RCM/giphy.gif"
        else:
            ctx["line"] = "No rush — I’ll keep it safe for later. 🤗"
        next_step = 4

    elif step == 4 and more:
        if more == "yes":
            ctx["line"] = "You’re my sunshine, my love, my everything. 🥰"
        else:
            ctx["line"] = "I’ll always be by your side. 💘"
        next_step = 5  # done

    if request.headers.get("Hx-Request") == "true":
        return templates.TemplateResponse(
            "partials/tw_v1_step.html",
            {"request": request, "step": next_step, "context": ctx},
        )

    return templates.TemplateResponse(
        "two_weeks_v1.html",
        {"request": request, "step": next_step, "context": ctx},
    )
