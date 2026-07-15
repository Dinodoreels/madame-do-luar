TRANSACTIONAL_EVENTS = {
    "welcome",
    "reading_completed",
    "payment_approved",
    "pos_venda",
    "password_reset",
    "daily_card",
}

MARKETING_EVENTS = {
    "marketing",
    "recompra",
    "reativacao",
    "daily_card_renewed",
    "carrinho_abandonado",
}


def automation_audience_type(event_type: str) -> str:
    if event_type in MARKETING_EVENTS:
        return "marketing"
    if event_type in TRANSACTIONAL_EVENTS:
        return "transactional"
    return "transactional"


def is_marketing_event(event_type: str) -> bool:
    return automation_audience_type(event_type) == "marketing"
