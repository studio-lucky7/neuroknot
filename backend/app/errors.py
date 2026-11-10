from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ValidationIssue(BaseModel):
    location: list[str | int]
    code: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    issues: list[ValidationIssue] | None = None


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _response(status_code: int, body: ErrorResponse, headers=None) -> JSONResponse:
    return JSONResponse(body.model_dump(exclude_none=True), status_code=status_code, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, error: AppError) -> JSONResponse:
        return _response(error.status_code, ErrorResponse(code=error.code, message=error.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        issues = [ValidationIssue(location=list(issue["loc"]), code=issue["type"]) for issue in error.errors()]
        return _response(422, ErrorResponse(code="validation_error", message="Invalid request.", issues=issues))

    @app.exception_handler(HTTPException)
    async def handle_http_error(_request: Request, error: HTTPException) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "HTTP request failed."
        return _response(error.status_code, ErrorResponse(code="http_error", message=message), error.headers)

    @app.exception_handler(Exception)
    async def handle_internal_error(_request: Request, _error: Exception) -> JSONResponse:
        return _response(500, ErrorResponse(code="internal_error", message="Internal server error."))
