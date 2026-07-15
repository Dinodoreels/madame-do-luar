from typing import Any, Optional

from pydantic import BaseModel, Field


class CrmRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class AdminCustomerTagRequest(CrmRequestModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    status: str = "active"


class AdminCustomerTagUpdateRequest(CrmRequestModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    status: Optional[str] = None


class AdminCustomerSegmentRequest(CrmRequestModel):
    name: str
    description: Optional[str] = None
    rules: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class AdminCustomerSegmentUpdateRequest(CrmRequestModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class AdminCustomerNoteRequest(CrmRequestModel):
    note: str
    visibility: str = "internal"


class AdminAssignTagRequest(CrmRequestModel):
    tag_id: str


class AdminSegmentTriggerRequest(CrmRequestModel):
    segment_id: str
    name: str
    event_type: str = "segment_entry"
    channel: Optional[str] = "whatsapp"
    template: Optional[str] = None
    rule_id: Optional[str] = None
    status: str = "active"


class AdminSegmentTriggerUpdateRequest(CrmRequestModel):
    name: Optional[str] = None
    event_type: Optional[str] = None
    channel: Optional[str] = None
    template: Optional[str] = None
    rule_id: Optional[str] = None
    status: Optional[str] = None
