from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/reconcile", tags=["炉批勾稽"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["reconcile"]
