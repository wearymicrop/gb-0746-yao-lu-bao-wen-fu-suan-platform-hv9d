from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.errors import BusinessError
from app.modules.m8_correction.schema import consistent_correction
from app.modules.m8_correction.service import detail, inspect, submit

router = APIRouter(prefix="/api", tags=["迟到更正"])


class Correction(BaseModel):
    base_run: str = ""
    recorder: str = ""
    corrections: object = None


@router.post("/corrections")
def create(request: Request, data: Correction):
    return submit(
        request.app.state.ledger, data.base_run, data.corrections, data.recorder
    )


@router.get("/corrections/{correction_id}")
def one(request: Request, correction_id: str):
    return detail(request.app.state.ledger, correction_id)


@router.get("/corrections/{correction_id}/export")
def export(request: Request, correction_id: str):
    record = detail(request.app.state.ledger, correction_id)
    if record["status"] != "FORMAL":
        raise BusinessError("NOT_FORMAL", "尚未对平的更正不能签发凭证", 409)
    if not consistent_correction(record):
        raise BusinessError("BUNDLE_MISMATCH", "更正结论摘要不一致", 409)
    return JSONResponse(
        record,
        headers={
            "Content-Disposition": f'attachment; filename="{correction_id}.json"'
        },
    )


@router.get("/runs/{run_id}/corrections")
def chain(request: Request, run_id: str):
    return inspect(request.app.state.ledger, run_id)
