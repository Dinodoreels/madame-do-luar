from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyticsEventRequest(BaseModel):
    event_name: str = Field(..., min_length=2, max_length=80)
    session_id: Optional[str] = Field(None, max_length=120)
    anonymous_id: Optional[str] = Field(None, max_length=120)
    page_url: Optional[str] = Field(None, max_length=600)
    referrer: Optional[str] = Field(None, max_length=600)
    source: str = Field("frontend", max_length=40)
    entity_type: Optional[str] = Field(None, max_length=80)
    entity_id: Optional[str] = Field(None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)
