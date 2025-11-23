# routers/first_love.py  (only the POST handler changed + one new JSON route)
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from base64 import b64encode
from services.first_love_model import predict as model_predict
from services.data_store import log_event, put_image
import os

router = APIRouter(tags=["first_love"])

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/first-love", response_class=HTMLResponse, name="first_love")
def first_love_get(request: Request):
    return templates.TemplateResponse(
        "first_love.html",
        {"request": request, "result": None, "gif_url": "/static/first_love/kiss.gif", "preview_img": None}
    )

@router.post("/first-love", response_class=HTMLResponse)
async def first_love_post(
    request: Request,
    text: str = Form(...),
    upload: UploadFile | None = File(None),
):
    text = (text or "").strip()
    result = None
    preview_img = None
    img_key = None

    if text:
        result = model_predict(text)

    if upload and upload.filename:
        raw = await upload.read()
        mime = upload.content_type or "image/png"
        preview_img = f"data:{mime};base64,{b64encode(raw).decode()}"
        # store original to S3 (if configured)
        try:
            key = put_image(raw, mime=mime)
            if key: img_key = key
        except Exception:
            pass

    # log to DynamoDB (if configured)
    try:
        if result and "error" not in result:
            client_ip = request.client.host if request.client else None
            log_event(text=text, theme=result["theme"], score=result["score"], engine=result.get("engine","?"),
                      img_key=img_key, ip=client_ip)
    except Exception:
        pass

    return templates.TemplateResponse(
        "first_love_ai.html",
        {"request": request, "result": result, "gif_url": "/static/first_love/kiss.gif", "preview_img": preview_img}
    )

# JSON API for AJAX or external use
@router.post("/api/first-love/classify")
async def api_first_love_classify(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse({"error":"empty"}, status_code=400)
    res = model_predict(text)
    # optional: log without image
    try:
        if res and "error" not in res:
            log_event(text=text, theme=res["theme"], score=res["score"], engine=res.get("engine","?"))
    except Exception:
        pass
    return JSONResponse(res)
