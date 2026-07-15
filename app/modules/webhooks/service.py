import hashlib
import json
import os


def normalize_webhook_status(payload: dict) -> tuple[str, str, str]:
    event_type = str(payload.get("type") or payload.get("event_type") or payload.get("event") or "").lower()
    raw_status = str(payload.get("status") or payload.get("payment_status") or "").lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    object_status = str(obj.get("status") or obj.get("payment_status") or "").lower()
    status_text = " ".join([event_type, raw_status, object_status])

    if "checkout.session.completed" in event_type or "approved" in status_text or "paid" in status_text or "succeeded" in status_text:
        return "approved", event_type or "payment.approved", obj.get("id") or payload.get("transaction_id")
    if "expired" in status_text:
        return "expired", event_type or "payment.expired", obj.get("id") or payload.get("transaction_id")
    if "cancel" in status_text:
        return "cancelled", event_type or "payment.cancelled", obj.get("id") or payload.get("transaction_id")
    if "refused" in status_text or "failed" in status_text or "error" in status_text:
        return "error", event_type or "payment.failed", obj.get("id") or payload.get("transaction_id")
    return "pending", event_type or "payment.updated", obj.get("id") or payload.get("transaction_id")


def pix_event_id(transaction_id: str, event_type: str, status: str, payload: dict) -> str:
    if payload.get("id") or payload.get("event_id"):
        return str(payload.get("id") or payload.get("event_id"))
    event_seed = f"{transaction_id}:{event_type}:{status}:{json.dumps(payload, sort_keys=True, default=str)}"
    return "pix_" + hashlib.sha256(event_seed.encode("utf-8")).hexdigest()[:32]


def pix_gateway(payload: dict) -> str:
    return str(payload.get("gateway") or os.getenv("PIX_GATEWAY", "generic"))
