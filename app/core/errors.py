from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, status_code: int, details: Any = None, request_id: str = None) -> dict:
    return {
        "success": False,
        "status": "error",
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
            "details": details or {},
            "request_id": request_id,
        },
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    request_id: str = None,
    headers: dict = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, status_code, details, request_id),
        headers=headers or None,
    )


def erro_http(status_code: int, code: str, message: str, details: Any = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})


def http_code_from_status(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        402: "PAYMENT_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        410: "GONE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        501: "NOT_IMPLEMENTED",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "API_ERROR")


def operational_event_type(code: str, path: str = "") -> str:
    code = (code or "").upper()
    path = (path or "").lower()
    if "AI" in code or "READING" in code:
        return "AI_ERROR"
    if "PAYMENT" in code or "PIX" in code or "checkout" in path or "payment" in path or "pagamento" in path:
        return "PAYMENT_ERROR"
    if "WEBHOOK" in code or "webhook" in path:
        return "WEBHOOK_ERROR"
    if "NOTIFICATION" in code or "WHATSAPP" in code or "EMAIL" in code or "message" in path:
        return "NOTIFICATION_ERROR"
    return "API_ERROR"
