# services/blog.py
import os, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from services.csv_store import append_csv_row, default_data_path, read_csv_rows, read_jsonl_rows, write_csv_rows

AWS_REGION = os.getenv("AWS_REGION") or "eu-north-1"
DDB_TABLE_POSTS = os.getenv("DDB_TABLE_POSTS", "echo_x_daniel_posts")
AUTO_CREATE = (os.getenv("AUTO_CREATE_TABLE", "0").strip() == "1")
DDB_ENDPOINT_URL = os.getenv("DDB_ENDPOINT_URL")
LOCAL_POSTS = Path(os.getenv("BLOG_CSV") or default_data_path("blog.csv"))
LEGACY_LOCAL_POSTS = Path(os.getenv("LOCAL_POSTS") or default_data_path("blog_posts.jsonl"))
POST_FIELDS = ["id", "author", "body", "cover_url", "created_at", "slug", "tags", "title", "updated_at"]

# DynamoDB disabled - using local CSV storage
USE_DDB = False

def _ddb():
    return None

def _posts_table():
    return None

# ------------ Models ------------
class PostIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=140)
    body: str = Field(..., min_length=1, max_length=20000)       # markdown/plaintext
    tags: Optional[str] = Field(None, max_length=120)            # comma-separated
    cover_url: Optional[str] = Field(None, max_length=400)

class PostOut(BaseModel):
    id: str
    slug: str
    created_at: str
    updated_at: str
    author: str
    title: str
    body: str
    tags: Optional[str] = None
    cover_url: Optional[str] = None

def _slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or uuid.uuid4().hex[:8]

def save_post(p: PostIn, author: str) -> PostOut:
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "slug": _slugify(p.title),
        "created_at": now,
        "updated_at": now,
        "author": author.strip() or "Unknown",
        "title": p.title.strip(),
        "body": p.body.strip(),
        "tags": (p.tags or "").strip() or None,
        "cover_url": (p.cover_url or "").strip() or None,
    }
    tab = _posts_table()
    if tab is not None:
        tab.put_item(Item=item)
    else:
        _bootstrap_csv_from_legacy()
        append_csv_row(LOCAL_POSTS, POST_FIELDS, item)
    return PostOut(**item)

def list_posts(limit: int = 50) -> List[PostOut]:
    tab = _posts_table()
    items = []
    if tab is not None:
        items = (tab.scan(Limit=1000) or {}).get("Items", [])
    else:
        items = _load_local_posts()
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [PostOut(**_normalize_post(it)) for it in items[:limit]]

def get_post_by_slug(slug: str) -> Optional[PostOut]:
    # Simple scan; fine for tiny private blog. (Add a GSI for slug later if you like.)
    for p in list_posts(limit=1000):
        if p.slug == slug:
            return p
    return None


def _load_local_posts() -> List[dict]:
    items = read_csv_rows(LOCAL_POSTS)
    if items:
        return items

    legacy_items = read_jsonl_rows(LEGACY_LOCAL_POSTS)
    if legacy_items:
        write_csv_rows(LOCAL_POSTS, POST_FIELDS, legacy_items)
    return legacy_items


def _bootstrap_csv_from_legacy() -> None:
    if LOCAL_POSTS.exists() and LOCAL_POSTS.stat().st_size > 0:
        return

    legacy_items = read_jsonl_rows(LEGACY_LOCAL_POSTS)
    if legacy_items:
        write_csv_rows(LOCAL_POSTS, POST_FIELDS, legacy_items)


def _normalize_post(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "slug": str(item.get("slug") or ""),
        "created_at": str(item.get("created_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
        "author": str(item.get("author") or ""),
        "title": str(item.get("title") or ""),
        "body": str(item.get("body") or ""),
        "tags": _optional_text(item.get("tags")),
        "cover_url": _optional_text(item.get("cover_url")),
    }


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
