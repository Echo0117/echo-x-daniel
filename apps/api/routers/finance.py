from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from services.finance_calc import FinanceInput, run_simulation, ALL_LOCATIONS

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/finance", response_class=HTMLResponse)
async def finance_page(request: Request):
    return templates.TemplateResponse(
        "finance.html",
        {"request": request, "all_locations": ALL_LOCATIONS},
    )


@router.post("/api/finance/run")
async def finance_run(data: FinanceInput):
    try:
        result = run_simulation(data)
        return result
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Simulation error: {exc}"})
