from app.modules.users.service import buscar_assinatura_ativa


def montar_status_pagamento(payment: dict, usuario: dict) -> dict:
    assinatura = buscar_assinatura_ativa(usuario["user_id"])
    status = payment.get("status") or "pending"
    return {
        "payment": {
            "payment_id": payment.get("payment_id"),
            "status": status,
            "tipo": payment.get("tipo"),
            "product_type": payment.get("product_type"),
            "product_name": payment.get("product_name"),
            "amount": payment.get("amount") or payment.get("valor"),
            "gateway": payment.get("gateway"),
            "gateway_ref": payment.get("gateway_ref"),
            "checkout_url": payment.get("checkout_url"),
            "credits_released": bool(payment.get("credits_released")),
            "approved_at": payment.get("approved_at"),
            "expires_at": payment.get("expires_at"),
            "error_message": payment.get("error_message"),
        },
        "assinatura": assinatura,
        "usuario": {
            "user_id": usuario.get("user_id"),
            "assinante": bool(usuario.get("assinante")),
            "plan_id": usuario.get("plan_id"),
            "credits_balance": usuario.get("credits_balance"),
        },
        "resolved": status in {"approved", "failed", "expired", "cancelled", "refused", "refunded", "error", "abandoned"},
    }
