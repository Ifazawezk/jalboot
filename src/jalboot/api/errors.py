"""The error envelope from API.md, with messages in the request's language."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

MESSAGES: dict[str, tuple[str, str]] = {
    "invalid_code": ("That code is not right.", "هذا الرمز غير صحيح."),
    "code_expired": ("That code has expired. Ask for a new one.", "انتهت صلاحية الرمز. اطلب رمزا جديدا."),
    "invalid_phone": ("That phone number is not valid.", "رقم الهاتف غير صحيح."),
    "too_many_attempts": ("Too many attempts. Please try again later.", "محاولات كثيرة. يرجى المحاولة لاحقا."),
    "too_many_streams": ("Too many open connections. Please close another page and try again.", "الاتصالات المفتوحة كثيرة. يُرجى إغلاق صفحة أخرى والمحاولة مرة أخرى."),
    "unauthorized": ("Please sign in.", "يرجى تسجيل الدخول."),
    "invalid_credentials": ("Wrong email or password.", "البريد الإلكتروني أو كلمة المرور غير صحيحة."),
    "csrf_failed": ("Your session needs refreshing. Please reload the page.", "يلزم تحديث الجلسة. يرجى إعادة تحميل الصفحة."),
    "approval_limit_exceeded": ("This refund needs a higher approval level.", "يحتاج هذا الاسترداد إلى مستوى موافقة أعلى."),
    "not_found": ("Not found.", "غير موجود."),
    "turn_in_progress": ("A reply is already on its way.", "الرد في الطريق إليك."),
    "duplicate_message": ("This message was already answered.", "تم الرد على هذه الرسالة من قبل."),
    "refund_already_decided": ("This refund has already been decided.", "تم البت في هذا الاسترداد من قبل."),
    "amount_exceeds_paid": ("This amount is more than can be refunded now.", "هذا المبلغ أكبر مما يمكن رده الآن."),
    "wallet_at_limit": ("This credit would pass the wallet limit, so it needs a different route.", "هذا الرصيد يتجاوز حد المحفظة، لذا يحتاج إلى طريقة أخرى."),
    "validation_error": ("That request is not valid.", "هذا الطلب غير صحيح."),
    "conversation_closed": ("This conversation is closed.", "تم إغلاق هذه المحادثة."),
    "internal_error": ("Something went wrong. Please try again.", "حدث خطأ. يرجى المحاولة مرة أخرى."),
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, *, retryable: bool = False, **extra: Any):
        super().__init__(code)
        self.status = status
        self.code = code
        self.retryable = retryable
        self.extra = extra


def language_of(request: Request) -> str:
    return "ar" if request.headers.get("accept-language", "").lower().startswith("ar") else "en"


def error_body(code: str, language: str, retryable: bool = False, **extra: Any) -> dict[str, Any]:
    pair = MESSAGES.get(code, MESSAGES["internal_error"])
    return {"error": {
        "code": code, "message": pair[1] if language == "ar" else pair[0], "retryable": retryable, **extra,
    }}


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, error: ApiError) -> JSONResponse:
        headers = {}
        if error.extra.get("retryAfterSeconds"):
            headers["Retry-After"] = str(error.extra["retryAfterSeconds"])
        return JSONResponse(
            status_code=error.status,
            content=error_body(error.code, language_of(request), error.retryable, **error.extra),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, _error: RequestValidationError) -> JSONResponse:
        # The details are dropped: they can echo a submitted password or code.
        return JSONResponse(status_code=422, content=error_body("validation_error", language_of(request)))

    @app.exception_handler(HTTPException)
    async def _http(request: Request, error: HTTPException) -> JSONResponse:
        code = {401: "unauthorized", 404: "not_found", 405: "not_found"}.get(error.status_code, "validation_error")
        return JSONResponse(status_code=error.status_code, content=jsonable_encoder(
            error_body(code, language_of(request))
        ))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=error_body("internal_error", language_of(request), True))
