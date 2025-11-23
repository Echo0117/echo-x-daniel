# services/messageboard.py
import os, json, uuid
from datetime import datetime, timezone
from typing import Optional, List
import boto3
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

# ---------------- 配置 ----------------
AWS_REGION = os.getenv("AWS_REGION") or "eu-north-1"
DDB_TABLE = os.getenv("DDB_TABLE", "echo_x_daniel_messages")
AUTO_CREATE = os.getenv("AUTO_CREATE_TABLE", "0") == "1"
LOCAL_STORE = os.getenv("LOCAL_STORE", "/mnt/data/messageboard.jsonl")

AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_USER_KEY = "user"

ENDPOINT = os.getenv("DDB_ENDPOINT_URL")
ddb = boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=ENDPOINT)

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
USE_DDB = True
try:
    import boto3
except Exception:
    USE_DDB = False

def _ddb_table():
    if not USE_DDB: return None
    ddb = boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=ENDPOINT)
    table = ddb.Table(DDB_TABLE)
    if AUTO_CREATE:
        try:
            table.load()
        except Exception:
            ddb.create_table(
                TableName=DDB_TABLE,
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                BillingMode="PAY_PER_REQUEST",
            ).wait_until_exists()
            table = ddb.Table(DDB_TABLE)
    return table

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
        os.makedirs(os.path.dirname(LOCAL_STORE), exist_ok=True)
        with open(LOCAL_STORE, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return MessageOut(**item)

def list_messages(limit: int = 20) -> List[MessageOut]:
    table = _ddb_table()
    items = []
    if table:
        scan = table.scan(Limit=1000)
        items = scan.get("Items", [])
    elif os.path.exists(LOCAL_STORE):
        with open(LOCAL_STORE, "r", encoding="utf-8") as f:
            items = [json.loads(x) for x in f.readlines()]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [MessageOut(**{k: it.get(k, "") for k in ["id", "created_at", "author", "title", "content"]}) for it in items[:limit]]
