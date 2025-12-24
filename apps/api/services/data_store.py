# services/data_store.py
# DynamoDB and S3 disabled - no external storage for first_love events
import os, time, uuid, hashlib

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
DDB_TABLE  = os.getenv("FIRST_LOVE_DDB_TABLE", "")     # e.g., first_love_events
S3_BUCKET  = os.getenv("FIRST_LOVE_S3_BUCKET", "")     # optional

_ddb = None  # boto3 removed
_s3  = None  # boto3 removed

def log_event(*, text:str, theme:str, score:str, engine:str, img_key:str|None=None, ip:str|None=None):
    # No-op: DynamoDB logging disabled
    return

def put_image(raw_bytes: bytes, mime: str = "image/png") -> str | None:
    # No-op: S3 storage disabled
    return None
