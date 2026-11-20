from fastapi import Request
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


async def response_for_error(request: Request, error: BusinessError):
    return JSONResponse(
        {"code": error.code, "message": error.message}, status_code=error.status
    )
