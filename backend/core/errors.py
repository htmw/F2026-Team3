"""API errors. Every error leaves the API as {"error": {"code", "message", "details"}}, the shape the frontend parses."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("acadmate")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


def not_found(what: str = "Resource") -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} not found.")


def forbidden(msg: str = "You don't have access to this.") -> ApiError:
    return ApiError(403, "FORBIDDEN", msg)


def conflict(msg: str) -> ApiError:
    return ApiError(409, "CONFLICT", msg)


def bad_request(msg: str, details: list | None = None) -> ApiError:
    return ApiError(400, "BAD_REQUEST", msg, details)


def unauthenticated(msg: str = "Sign in to continue.") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", msg)


def error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


HTTP_CODES = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 429: "RATE_LIMITED"}
HTTP_MESSAGES = {404: "Not found.", 405: "This method isn't allowed here."}


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return "This value isn't valid."
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def friendly(error: dict) -> str:
    """A user-facing sentence for one Pydantic validation error."""
    kind, ctx, msg = error.get("type", ""), error.get("ctx") or {}, error.get("msg", "")
    field = str(error["loc"][-1]) if error.get("loc") else ""
    if kind == "missing":
        return "This field is required."
    if kind == "value_error" and "email" in msg.lower():
        return "Enter a valid email address."
    if kind == "value_error":  # our own validators' ValueError text, without Pydantic's "Value error, " prefix
        return _sentence(msg.removeprefix("Value error, "))
    if kind == "string_too_short":
        if ctx.get("min_length") == 1:
            return "Enter your password." if field == "password" else "This field is required."
        if field == "password":
            return f"Use at least {ctx.get('min_length')} characters for your password."
        return f"Must be at least {ctx.get('min_length')} characters."
    if kind == "string_too_long":
        return f"Must be at most {ctx.get('max_length')} characters."
    if kind in ("int_parsing", "int_type", "float_parsing", "float_type", "decimal_parsing"):
        return "Enter a number."
    if kind == "literal_error":
        return f"Choose one of: {ctx.get('expected')}."
    return _sentence(msg)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": str(err["loc"][-1]) if err.get("loc") else "", "message": friendly(err)} for err in exc.errors()]
        return JSONResponse(error_body("VALIDATION_ERROR", "Check the highlighted fields.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = HTTP_CODES.get(exc.status_code, "BAD_REQUEST" if exc.status_code < 500 else "INTERNAL")
        detail = exc.detail if isinstance(exc.detail, str) else ""
        message = HTTP_MESSAGES.get(exc.status_code) or (_sentence(detail) if detail else "Request failed.")
        return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(error_body("INTERNAL", "Something went wrong on our side. Try again."), status_code=500)
