from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from .repository import AnalyticsRepository


analytics_repository = AnalyticsRepository()

TRACKED_EVENTS = {
    "page_view",
    "signup_started",
    "signup_completed",
    "login_success",
    "login_failed",
    "onboarding_started",
    "onboarding_completed",
    "daily_card_started",
    "daily_card_completed",
    "reading_started",
    "reading_ai_started",
    "reading_ai_failed",
    "reading_completed",
    "credits_insufficient",
    "checkout_started",
    "checkout_pix_generated",
    "payment_approved",
    "payment_failed",
    "payment_abandoned",
    "subscription_started",
    "subscription_cancel_requested",
    "subscription_cancelled",
    "feedback_submitted",
    "price_test_assigned",
    "secondary_offer_viewed",
    "ritual_viewed",
    "ritual_purchased",
    "coupon_applied",
    "coupon_failed",
    "profile_updated",
    "whatsapp_opt_in",
    "whatsapp_opt_out",
    "email_opt_in",
    "automation_sent",
    "automation_failed",
    "admin_login",
    "admin_payment_manual_approved",
    "admin_export_created",
    "api_error",
    "rate_limited",
}


def normalize_event_name(event_name: str) -> str:
    return str(event_name or "").strip().lower().replace("-", "_").replace(" ", "_")


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def track_event(body, request, user: Optional[dict] = None, admin: Optional[dict] = None, repository: AnalyticsRepository = analytics_repository) -> dict:
    event_name = normalize_event_name(body.event_name)
    if event_name not in TRACKED_EVENTS:
        return {"accepted": False, "error": "EVENT_NOT_ALLOWED", "event_name": event_name}

    payload = {
        "event_name": event_name,
        "user_id": (user or {}).get("user_id"),
        "admin_id": (admin or {}).get("user_id"),
        "session_id": body.session_id,
        "anonymous_id": body.anonymous_id,
        "page_url": body.page_url,
        "referrer": body.referrer,
        "source": body.source or "frontend",
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "metadata": body.metadata or {},
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    event = repository.create_event(payload)
    if event.get("erro"):
        repository.log(
            "ANALYTICS_EVENT_FAILED",
            "Falha ao registrar evento de analytics.",
            user_id=payload.get("user_id"),
            admin_id=payload.get("admin_id"),
            metadata={"event_name": event_name, "erro": event.get("erro")},
            severity="warning",
            ip_address=payload.get("ip_address"),
            user_agent=payload.get("user_agent"),
        )
        return {"accepted": False, "error": event.get("erro"), "event_name": event_name}
    return {"accepted": True, "event_name": event_name, "event_id": event.get("event_id")}


def track_server_event(
    event_name: str,
    *,
    user_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    source: str = "backend",
    repository: AnalyticsRepository = analytics_repository,
) -> dict:
    name = normalize_event_name(event_name)
    if name not in TRACKED_EVENTS:
        return {"accepted": False, "error": "EVENT_NOT_ALLOWED", "event_name": name}
    event = repository.create_event({
        "event_name": name,
        "user_id": user_id,
        "admin_id": admin_id,
        "source": source,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
    })
    if event.get("erro"):
        repository.log(
            "ANALYTICS_EVENT_FAILED",
            "Falha ao registrar evento server-side de analytics.",
            user_id=user_id,
            admin_id=admin_id,
            metadata={"event_name": name, "erro": event.get("erro")},
            severity="warning",
        )
        return {"accepted": False, "error": event.get("erro"), "event_name": name}
    return {"accepted": True, "event_name": name, "event_id": event.get("event_id")}


def events_since(days: int = 30, repository: AnalyticsRepository = analytics_repository) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return repository.list_events(filters=f"created_at=gte.{cutoff}", limit=10000, order="created_at.desc")


def analytics_summary(days: int = 30, repository: AnalyticsRepository = analytics_repository) -> dict:
    events = events_since(days, repository)
    counts = Counter(event.get("event_name") for event in events)
    sessions_by_event = defaultdict(set)
    users_by_event = defaultdict(set)
    for event in events:
        name = event.get("event_name")
        session_key = event.get("session_id") or event.get("anonymous_id")
        user_key = event.get("user_id")
        if session_key:
            sessions_by_event[name].add(session_key)
        if user_key:
            users_by_event[name].add(user_key)

    funnel = {
        "cadastro": {
            "iniciado": counts["signup_started"],
            "concluido": counts["signup_completed"],
            "taxa": rate(counts["signup_completed"], counts["signup_started"]),
        },
        "leitura": {
            "iniciada": counts["reading_started"],
            "ia_iniciada": counts["reading_ai_started"],
            "concluida": counts["reading_completed"],
            "falha_ia": counts["reading_ai_failed"],
            "taxa": rate(counts["reading_completed"], counts["reading_started"]),
        },
        "pagamento": {
            "checkout": counts["checkout_started"],
            "pix_gerado": counts["checkout_pix_generated"],
            "aprovado": counts["payment_approved"],
            "falhou": counts["payment_failed"],
            "abandonado": counts["payment_abandoned"],
            "taxa_aprovacao": rate(counts["payment_approved"], counts["checkout_started"]),
            "taxa_abandono": rate(counts["payment_abandoned"], counts["checkout_started"]),
        },
    }
    return {
        "days": days,
        "events_total": len(events),
        "event_counts": dict(counts),
        "unique_sessions": {name: len(values) for name, values in sessions_by_event.items()},
        "unique_users": {name: len(values) for name, values in users_by_event.items()},
        "funnel": funnel,
        "retention": retention(events),
    }


def retention(events: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    active_7 = set()
    active_30 = set()
    by_user = defaultdict(set)
    for event in events:
        user_key = event.get("user_id") or event.get("anonymous_id") or event.get("session_id")
        when = parse_dt(event.get("created_at"))
        if not user_key or not when:
            continue
        by_user[user_key].add(str(when.date()))
        if when >= now - timedelta(days=7):
            active_7.add(user_key)
        if when >= now - timedelta(days=30):
            active_30.add(user_key)
    base = len(by_user)
    recurrent = sum(1 for dates in by_user.values() if len(dates) >= 2)
    return {
        "tracked_users": base,
        "active_7_days": len(active_7),
        "active_30_days": len(active_30),
        "recurrent_users": recurrent,
        "retention_7_rate": rate(len(active_7), base),
        "retention_30_rate": rate(len(active_30), base),
        "recurrent_rate": rate(recurrent, base),
    }


def rate(part: int, total: int) -> float:
    return round((part / total) * 100, 2) if total else 0.0
