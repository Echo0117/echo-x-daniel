# services/messageboard.py
import os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from services.csv_store import append_csv_row, default_data_path, read_csv_rows, read_jsonl_rows, write_csv_rows

# ---------------- 配置 ----------------
AWS_REGION = os.getenv("AWS_REGION") or "eu-north-1"
DDB_TABLE = os.getenv("DDB_TABLE", "echo_x_daniel_messages")
AUTO_CREATE = os.getenv("AUTO_CREATE_TABLE", "0") == "1"
LOCAL_STORE = Path(os.getenv("MESSAGEBOARD_CSV") or default_data_path("messageboard.csv"))
LEGACY_LOCAL_STORE = Path(os.getenv("LOCAL_STORE") or default_data_path("messageboard.jsonl"))
MESSAGE_FIELDS = ["id", "author", "content", "created_at", "title"]

AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_USER_KEY = "user"

# ---------------- 模型 ----------------
class MessageIn(BaseModel):
    author: str = Field(..., min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=4000)
    title: Optional[str] = Field(None, max_length=140)

class MessageOut(BaseModel):
    id: str
    created_at: str
    author: str
    title: Optional[str] = None
    content: str

# ---------------- Auth ----------------
async def require_auth(request: Request):
    if not request.session.get(SESSION_USER_KEY):
        nxt = request.url.path
        # Raise an exception (not a Response) so FastAPI can short-circuit and send the redirect
        raise HTTPException(
            status_code=303,  # See Other
            headers={"Location": f"/login?next={nxt}"}
        )

def check_login(username: str, password: str) -> bool:
    return (
        username.strip().lower() == (AUTH_USERNAME or "").lower()
        and password == AUTH_PASSWORD
    )

# ---------------- 存储 ----------------
# DynamoDB disabled - using local CSV storage
USE_DDB = False

def _ddb_table():
    return None

def save_message(msg: MessageIn, request: Request) -> MessageOut:
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "author": msg.author.strip(),
        "title": (msg.title or "").strip() or None,
        "content": msg.content.strip(),
    }
    table = _ddb_table()
    if table:
        table.put_item(Item=item)
    else:
        _bootstrap_csv_from_legacy()
        append_csv_row(LOCAL_STORE, MESSAGE_FIELDS, item)
    return MessageOut(**item)

def list_messages(limit: int = 20) -> List[MessageOut]:
    table = _ddb_table()
    items = []
    if table:
        scan = table.scan(Limit=1000)
        items = scan.get("Items", [])
    else:
        items = _load_local_messages()
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [MessageOut(**_normalize_message(it)) for it in items[:limit]]


def _load_local_messages() -> List[dict]:
    items = read_csv_rows(LOCAL_STORE)
    if items:
        return items

    legacy_items = read_jsonl_rows(LEGACY_LOCAL_STORE)
    if legacy_items:
        write_csv_rows(LOCAL_STORE, MESSAGE_FIELDS, legacy_items)
    return legacy_items


def _bootstrap_csv_from_legacy() -> None:
    if LOCAL_STORE.exists() and LOCAL_STORE.stat().st_size > 0:
        return

    legacy_items = read_jsonl_rows(LEGACY_LOCAL_STORE)
    if legacy_items:
        write_csv_rows(LOCAL_STORE, MESSAGE_FIELDS, legacy_items)


def _normalize_message(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "created_at": str(item.get("created_at") or ""),
        "author": str(item.get("author") or ""),
        "title": _optional_text(item.get("title")),
        "content": str(item.get("content") or ""),
    }


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
