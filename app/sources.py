import json

from fastapi import APIRouter, Request

from app.config import MAX_SOURCE_BYTES
from app.errors import BusinessError
from app.manifest import digest
from app.pipeline import calculate

router = APIRouter(prefix="/api/sources", tags=["数据来源"])


@router.post("")
async def upload(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_SOURCE_BYTES:
            raise BusinessError("SOURCE_TOO_LARGE", "数据超过 512 KiB", 413)
    try:
        data = json.loads(body.decode("utf-8-sig"))
        checksum = digest(data)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise BusinessError("BAD_JSON", "请输入有效的 UTF-8 JSON") from error
    if not isinstance(data, dict):
        raise BusinessError("BAD_SOURCE", "数据根节点须为对象")
    calculate(data)
    source = "src-" + checksum
    reused = request.app.state.ledger.put_source(source, data)
    return {"source": source, "sha256": checksum, "reused": reused}
