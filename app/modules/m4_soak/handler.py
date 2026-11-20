from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/soak", tags=["保温计时"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["soak"]
