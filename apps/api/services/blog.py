# services/blog.py
import os, re, json, uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Request

AWS_REGION = os.getenv("AWS_REGION") or "eu-north-1"
DDB_TABLE_POSTS = os.getenv("DDB_TABLE_POSTS", "echo_x_daniel_posts")
AUTO_CREATE = (os.getenv("AUTO_CREATE_TABLE", "0").strip() == "1")
DDB_ENDPOINT_URL = os.getenv("DDB_ENDPOINT_URL")
LOCAL_POSTS = os.getenv("LOCAL_POSTS", "/mnt/data/blog_posts.jsonl")

USE_DDB = True
try:
    import boto3
except Exception:
    USE_DDB = False
    boto3 = None

def _ddb():
    if not USE_DDB or boto3 is None:
        return None
    return boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=DDB_ENDPOINT_URL)

def _posts_table():
    res = _ddb()
    if res is None:
        return None
    tab = res.Table(DDB_TABLE_POSTS)
    if AUTO_CREATE:
        try:
            tab.load()
        except Exception:
            res.create_table(
                TableName=DDB_TABLE_POSTS,
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
            ).wait_until_exists()
            tab = res.Table(DDB_TABLE_POSTS)
    return tab

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
        os.makedirs(os.path.dirname(LOCAL_POSTS), exist_ok=True)
        with open(LOCAL_POSTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return PostOut(**item)

def list_posts(limit: int = 50) -> List[PostOut]:
    tab = _posts_table()
    items = []
    if tab is not None:
        items = (tab.scan(Limit=1000) or {}).get("Items", [])
    elif os.path.exists(LOCAL_POSTS):
        with open(LOCAL_POSTS, "r", encoding="utf-8") as f:
            items = [json.loads(x) for x in f]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [PostOut(**{
        "id": it.get("id",""),
        "slug": it.get("slug",""),
        "created_at": it.get("created_at",""),
        "updated_at": it.get("updated_at",""),
        "author": it.get("author",""),
        "title": it.get("title",""),
        "body": it.get("body",""),
        "tags": it.get("tags"),
        "cover_url": it.get("cover_url"),
    }) for it in items[:limit]]

def get_post_by_slug(slug: str) -> Optional[PostOut]:
    # Simple scan; fine for tiny private blog. (Add a GSI for slug later if you like.)
    for p in list_posts(limit=1000):
        if p.slug == slug:
            return p
    return None
