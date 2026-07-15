from typing import Any, Optional

from pydantic import BaseModel, Field


class AdminRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class AdminUserStatusRequest(AdminRequestModel):
    status: str
    reason: Optional[str] = None


class AdminCreditRequest(AdminRequestModel):
    amount: int
    type: str = "add"
    reason: str
    related_payment_id: Optional[str] = None
    related_reading_id: Optional[str] = None
    expires_at: Optional[str] = None


class AdminManualPaymentRequest(AdminRequestModel):
    reason: Optional[str] = None


class AdminPaymentReprocessRequest(AdminRequestModel):
    webhook_payload: Optional[dict[str, Any]] = None
    reason: Optional[str] = None


class AdminPlanRequest(AdminRequestModel):
    name: str
    description: Optional[str] = None
    price: float = 0
    credits: int = 0
    duration_days: Optional[int] = None
    benefits: list[Any] = Field(default_factory=list)
    status: str = "active"


class AdminPlanUpdateRequest(AdminRequestModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    credits: Optional[int] = None
    duration_days: Optional[int] = None
    benefits: Optional[list[Any]] = None
    status: Optional[str] = None


class AdminCreditPackageRequest(AdminRequestModel):
    name: str
    description: Optional[str] = None
    credits: int
    price: float
    bonus_credits: int = 0
    validity_days: Optional[int] = None
    benefits: list[Any] = Field(default_factory=list)
    status: str = "active"


class AdminCreditPackageUpdateRequest(AdminRequestModel):
    name: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    bonus_credits: Optional[int] = None
    validity_days: Optional[int] = None
    benefits: Optional[list[Any]] = None
    status: Optional[str] = None


class AdminCouponRequest(AdminRequestModel):
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    applies_to: str = "all"
    event_type: Optional[str] = None
    max_uses: Optional[int] = None
    minimum_amount: float = 0
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    status: str = "active"


class AdminCouponUpdateRequest(AdminRequestModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    applies_to: Optional[str] = None
    event_type: Optional[str] = None
    max_uses: Optional[int] = None
    minimum_amount: Optional[float] = None
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    status: Optional[str] = None


class AdminUserPlanRequest(AdminRequestModel):
    plan_id: Optional[str] = None
    reason: Optional[str] = None


class AdminPromptRequest(AdminRequestModel):
    name: str
    reading_type: str
    content: str
    version: int = 1
    status: str = "active"


class AdminPromptUpdateRequest(AdminRequestModel):
    name: Optional[str] = None
    reading_type: Optional[str] = None
    content: Optional[str] = None
    version: Optional[int] = None
    status: Optional[str] = None


class AdminSettingsUpdateRequest(AdminRequestModel):
    values: dict[str, Any]


class AdminMaintenanceRequest(AdminRequestModel):
    enabled: bool
    message: Optional[str] = None


class AdminQueueRequest(AdminRequestModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    related_payment_id: Optional[str] = None
    related_reading_id: Optional[str] = None
    error_message: Optional[str] = None
    delay_minutes: int = 0
    max_attempts: Optional[int] = None


class AdminJobProcessRequest(AdminRequestModel):
    limit: int = 25
    dry_run: bool = False


class AdminJobRetryRequest(AdminRequestModel):
    reason: Optional[str] = None


class AdminAlertStatusRequest(AdminRequestModel):
    status: str


class AdminMessageResendRequest(AdminRequestModel):
    message: Optional[str] = None


class AdminRitualRequest(AdminRequestModel):
    nome: str
    tema: Optional[str] = None
    descricao: Optional[str] = None
    preco: float = 0
    pdf_url: Optional[str] = None
    audio_url: Optional[str] = None
    ativo: bool = True


class AdminRitualUpdateRequest(AdminRequestModel):
    nome: Optional[str] = None
    tema: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = None
    pdf_url: Optional[str] = None
    audio_url: Optional[str] = None
    ativo: Optional[bool] = None


class AdminCampaignRequest(AdminRequestModel):
    name: str
    event_type: str = "marketing"
    channel: str = "whatsapp"
    subject: Optional[str] = None
    template: str
    delay_minutes: int = 0
    status: str = "active"


class AdminCampaignUpdateRequest(AdminRequestModel):
    name: Optional[str] = None
    event_type: Optional[str] = None
    status: Optional[str] = None
