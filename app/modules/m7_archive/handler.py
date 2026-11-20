from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.errors import BusinessError
from app.modules.m7_archive.bundle import consistent
from app.modules.m7_archive.service import archive, rerun

router = APIRouter(prefix="/api/runs", tags=["归档与凭证"])


class Submission(BaseModel):
    source: str = ""
    operator: str = ""


@router.post("")
def create(request: Request, data: Submission):
    return archive(request.app.state.ledger, data.source, data.operator)


@router.get("/{run_id}")
def detail(request: Request, run_id: str):
    return request.app.state.ledger.run(run_id)


@router.post("/{run_id}/rerun")
def repeat(request: Request, run_id: str):
    return rerun(request.app.state.ledger, run_id)


@router.get("/{run_id}/export")
def export(request: Request, run_id: str):
    record = request.app.state.ledger.run(run_id)
    if not consistent(record):
        raise BusinessError("BUNDLE_MISMATCH", "凭证摘要不一致", 409)
    return JSONResponse(
        record, headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'}
    )
