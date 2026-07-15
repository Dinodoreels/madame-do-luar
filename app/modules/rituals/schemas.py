from typing import Optional

from pydantic import BaseModel


class RitualPurchaseRequest(BaseModel):
    class Config:
        extra = "forbid"

    coupon_code: Optional[str] = None
    offer_context: Optional[str] = None
