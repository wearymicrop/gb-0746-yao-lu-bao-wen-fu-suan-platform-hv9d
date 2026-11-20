from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/gaps", tags=["断档复判"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["gaps"]
