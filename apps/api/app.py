from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import home, letters, poetry, surprises, playful, perseids, first_love, eighteen_days, three_weeks, messageboard, blog, christmas, finance
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
import os

app = FastAPI(title="Echo × Daniel", version="2.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)  # ensure it exists

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-32-bytes-min")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=False,         # True in prod behind HTTPS; False for local http://127.0.0.1
    same_site="lax",
)

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)

# routers
app.include_router(home.router)
app.include_router(letters.router,   prefix="/letters", tags=["letters"])
app.include_router(poetry.router,    prefix="/poetry",  tags=["poetry"])
app.include_router(surprises.router, tags=["surprises"])
app.include_router(playful.router,   tags=["play"])  # <-- this
app.include_router(perseids.router, tags=["perseids"])
app.include_router(first_love.router, tags=["first-love"])
app.include_router(eighteen_days.router)
app.include_router(three_weeks.router)
app.include_router(messageboard.router)
app.include_router(blog.router)
app.include_router(christmas.router, tags=["christmas"])
app.include_router(finance.router,   tags=["finance"])

@app.get("/health/live")
def live():
    return {"status":"ok"}


@app.get("/health/ready")
def ready():
    return {"status":"ready"}