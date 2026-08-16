from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": getattr(exc, "code", "http_error"),
                    "message": exc.detail,
                    "details": getattr(exc, "details", {}),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "入力内容を確認してください",
                    # loc の先頭は "body" / "query" などの出所なので落とし、残りをつないで項目名にする
                    "details": {
                        ".".join(str(part) for part in error["loc"][1:]): error["msg"]
                        for error in exc.errors()
                    },
                }
            },
        )
