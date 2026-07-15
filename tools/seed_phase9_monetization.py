"""
Seed inicial da Fase 9: rituais, cupons e ofertas.

Rode depois de aplicar architecture/schema.sql no Supabase real:
  python tools/seed_phase9_monetization.py
"""

from __future__ import annotations

import db_client


RITUALS = [
    {
        "nome": "Ritual Gratuito de Clareza Lunar",
        "tema": "clareza",
        "descricao": "Pratica curta para organizar pensamentos apos uma leitura e transformar intuicao em uma decisao simples.",
        "preco": 0,
        "pdf_url": "https://example.com/madame-do-luar/ritual-clareza-lunar.pdf",
        "audio_url": "",
        "ativo": True,
    },
    {
        "nome": "Ritual de Protecao e Limpeza Energetica",
        "tema": "protecao",
        "descricao": "Roteiro completo para encerrar ciclos pesados, proteger o campo energetico e criar um marco simbolico de recomeco.",
        "preco": 30,
        "pdf_url": "https://example.com/madame-do-luar/ritual-protecao.pdf",
        "audio_url": "https://example.com/madame-do-luar/ritual-protecao.mp3",
        "ativo": True,
    },
    {
        "nome": "Ritual de Atracao Amorosa Consciente",
        "tema": "amor",
        "descricao": "Pratica guiada para alinhar desejo, autocuidado e limites antes de agir em temas afetivos.",
        "preco": 40,
        "pdf_url": "https://example.com/madame-do-luar/ritual-amor.pdf",
        "audio_url": "https://example.com/madame-do-luar/ritual-amor.mp3",
        "ativo": True,
    },
]

COUPONS = [
    {
        "code": "RITUAL10",
        "description": "Upsell apos leitura: 10% em rituais pagos.",
        "discount_type": "percent",
        "discount_value": 10,
        "applies_to": "ritual",
        "event_type": "after_reading",
        "minimum_amount": 1,
        "status": "active",
    },
    {
        "code": "LUA5",
        "description": "Desconto fixo para campanha de reativacao.",
        "discount_type": "fixed",
        "discount_value": 5,
        "applies_to": "ritual",
        "event_type": "downsell",
        "minimum_amount": 20,
        "status": "active",
    },
]


def upsert_by_field(table: str, field: str, value: str, payload: dict) -> tuple[str, dict]:
    current = db_client.buscar_por_id(table, field, value)
    if current:
        return "exists", current
    created = db_client.criar_registro(table, payload)
    if "erro" in created and table == "coupons":
        legacy = {k: v for k, v in payload.items() if k not in ("applies_to", "event_type")}
        created = db_client.criar_registro(table, legacy)
    return ("error" if "erro" in created else "created"), created


def main() -> int:
    results = []
    for ritual in RITUALS:
        results.append(("ritual", ritual["nome"], *upsert_by_field("rituals", "nome", ritual["nome"], ritual)))
    for coupon in COUPONS:
        coupon = dict(coupon)
        coupon["code"] = db_client.normalizar_codigo_cupom(coupon["code"])
        results.append(("coupon", coupon["code"], *upsert_by_field("coupons", "code", coupon["code"], coupon)))

    failed = False
    for kind, name, status, payload in results:
        print(f"{kind} {name}: {status}")
        if status == "error":
            failed = True
            print(payload.get("erro"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
