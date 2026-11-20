from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/alignment", tags=["热区对齐"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["alignment"]
