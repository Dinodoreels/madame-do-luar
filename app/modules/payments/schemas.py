from typing import Optional

from pydantic import BaseModel


class PaymentsRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class CheckoutRequest(PaymentsRequestModel):
    user_id: Optional[str] = None
    plano: str


class SubscriptionCancelRequest(PaymentsRequestModel):
    reason: Optional[str] = None


class PixCreateRequest(PaymentsRequestModel):
    product_type: str
    product_id: str
    coupon_code: Optional[str] = None
