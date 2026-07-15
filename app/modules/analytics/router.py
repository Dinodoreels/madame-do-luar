from fastapi import APIRouter, Depends, Request

from app.core.security import admin_atual, usuario_atual_opcional

from .schemas import AnalyticsEventRequest
from .use_cases import TRACKED_EVENTS, analytics_summary, track_event


router = APIRouter(tags=["analytics"])


@router.post("/api/analytics/events")
async def create_analytics_event(body: AnalyticsEventRequest, request: Request, user: dict | None = Depends(usuario_atual_opcional)):
    return track_event(body, request, user=user)


@router.get("/api/analytics/events/catalog")
async def analytics_event_catalog():
    return {"events": sorted(TRACKED_EVENTS)}


@router.get("/admin/analytics/summary")
@router.get("/api/admin/analytics/summary")
async def admin_analytics_summary(days: int = 30, admin: dict = Depends(admin_atual)):
    return analytics_summary(days=min(max(days, 1), 365))
