# routers/blog.py
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List

from services.messageboard import require_auth, SESSION_USER_KEY  # reuse auth/session
from services.blog import PostIn, PostOut, save_post, list_posts, get_post_by_slug

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/blog", name="blog_index", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def blog_index(request: Request):
    posts = list_posts(limit=100)
    return templates.TemplateResponse("blog_index.html", {"request": request, "posts": posts})

@router.get("/blog/new", name="blog_new", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def blog_new(request: Request):
    return templates.TemplateResponse("blog_form.html", {"request": request})

@router.get("/blog/{slug}", name="blog_view", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def blog_view(request: Request, slug: str):
    post = get_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse("blog_view.html", {"request": request, "post": post})

@router.post("/api/blog", response_model=PostOut, dependencies=[Depends(require_auth)])
async def blog_create(request: Request, data: PostIn):
    # author from session (the username you logged in with)
    author = request.session.get(SESSION_USER_KEY, "Unknown")
    post = save_post(data, author=author)
    return post
