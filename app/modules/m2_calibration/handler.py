from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/calibration", tags=["热电偶校正"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["calibration"]
