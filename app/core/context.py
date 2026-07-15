from fastapi import Request
from pydantic import BaseModel


def request_context(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def clean_payload(model: BaseModel) -> dict:
    return model.dict(exclude_none=True)
