# services/data_store.py
import os, time, uuid, hashlib, boto3

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
DDB_TABLE  = os.getenv("FIRST_LOVE_DDB_TABLE", "")     # e.g., first_love_events
S3_BUCKET  = os.getenv("FIRST_LOVE_S3_BUCKET", "")     # optional

_ddb = boto3.resource("dynamodb", region_name=AWS_REGION) if DDB_TABLE else None
_s3  = boto3.client("s3",         region_name=AWS_REGION) if S3_BUCKET else None

def log_event(*, text:str, theme:str, score:str, engine:str, img_key:str|None=None, ip:str|None=None):
    if not _ddb: return
    item = {
        "id": str(uuid.uuid4()),
        "ts": int(time.time()),
        "text": text[:2000],
        "theme": theme, "score": score, "engine": engine,
    }
    if img_key: item["img_key"] = img_key
    if ip: item["ip_hash"] = hashlib.sha256(ip.encode()).hexdigest()[:16]
    _ddb.Table(DDB_TABLE).put_item(Item=item)

def put_image(raw_bytes: bytes, mime: str = "image/png") -> str | None:
    if not _s3: return None
    key = f"memories/{int(time.time())}-{uuid.uuid4().hex}"
    _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=raw_bytes, ContentType=mime, ACL="private")
    return key
