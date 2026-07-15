from .repository import RitualsRepository


repository = RitualsRepository()


COMMERCIAL_THEME_KEYWORDS = {
    "amor": ("amor", "relacionamento", "casamento", "ex", "paixao", "sentimento"),
    "protecao": ("protecao", "limpeza", "energia", "inveja", "medo", "ansiedade", "bloqueio"),
    "clareza": ("clareza", "decisao", "duvida", "caminho", "escolha", "direcao"),
    "carreira": ("carreira", "trabalho", "emprego", "negocio", "dinheiro", "prosperidade"),
}


def custo_creditos_ritual(produto: dict) -> int:
    valor = max(0, float(produto.get("amount") or 0))
    inteiro = int(valor)
    return inteiro if valor == inteiro else inteiro + 1


def criar_compra_ritual_creditos(user_id: str, ritual_id: str, status: str, credits_spent: int = 0, coupon_code: str = None) -> dict:
    compras = repository.list_purchases(filters=f"user_id=eq.{user_id}&ritual_id=eq.{ritual_id}&status=in.(pending,approved)", limit=1)
    if compras:
        return {**compras[0], "ja_comprado": True}
    payload = {"user_id": user_id, "ritual_id": ritual_id, "status": status, "credits_spent": credits_spent, "coupon_code": coupon_code}
    compra = repository.create_purchase(payload)
    if "erro" in compra and any(field in str(compra["erro"]) for field in ("credits_spent", "coupon_code")):
        payload.pop("credits_spent", None)
        payload.pop("coupon_code", None)
        compra = repository.create_purchase(payload)
    return compra


def ritual_public_payload(ritual: dict) -> dict:
    custo = custo_creditos_ritual({"amount": ritual.get("preco")})
    return {
        "ritual_id": ritual.get("ritual_id"),
        "nome": ritual.get("nome"),
        "tema": ritual.get("tema"),
        "descricao": ritual.get("descricao"),
        "preco": ritual.get("preco"),
        "creditos": custo,
        "custo_creditos": custo,
        "moeda": "creditos",
        "gratuito": custo <= 0,
        "pdf_url": ritual.get("pdf_url") if custo <= 0 else None,
        "audio_url": ritual.get("audio_url") if custo <= 0 else None,
    }


def tema_comercial_usuario(user_id: str) -> str:
    perguntas = repository.questions.list(
        select="pergunta,tema,criado_em",
        filters=f"user_id=eq.{user_id}",
        limit=5,
        order="criado_em.desc",
    )
    for pergunta in perguntas:
        tema = str(pergunta.get("tema") or "").strip().lower()
        if tema:
            return tema
        texto = str(pergunta.get("pergunta") or "").lower()
        for candidato, keywords in COMMERCIAL_THEME_KEYWORDS.items():
            if any(keyword in texto for keyword in keywords):
                return candidato
    return "clareza"


def selecionar_ofertas_pos_leitura(user_id: str) -> dict:
    tema = tema_comercial_usuario(user_id)
    rituais = repository.list_active_rituals(limit=100)

    def pontuar(ritual: dict, gratuito: bool) -> tuple[int, float]:
        preco = float(ritual.get("preco") or 0)
        ritual_gratuito = preco <= 0
        if ritual_gratuito != gratuito:
            return (-1000, -preco)
        pontos = 0
        ritual_tema = str(ritual.get("tema") or "").lower()
        texto = f"{ritual.get('nome') or ''} {ritual.get('descricao') or ''}".lower()
        if ritual_tema == tema:
            pontos += 40
        for keyword in COMMERCIAL_THEME_KEYWORDS.get(tema, (tema,)):
            if keyword and keyword in texto:
                pontos += 8
        return (pontos, preco)

    pagos = [r for r in rituais if float(r.get("preco") or 0) > 0]
    gratuitos = [r for r in rituais if float(r.get("preco") or 0) <= 0]
    pago = max(pagos, key=lambda r: pontuar(r, gratuito=False), default=None)
    gratuito = max(gratuitos, key=lambda r: pontuar(r, gratuito=True), default=None)

    cupons = repository.coupons.list(
        select="*",
        filters="status=eq.active&applies_to=in.(all,ritual)&event_type=eq.after_reading",
        limit=5,
    )
    cupom = cupons[0] if cupons else repository.get_coupon_by_code("RITUAL10")
    return {
        "tema": tema,
        "upsell": ritual_public_payload(pago) if pago else None,
        "downsell": ritual_public_payload(gratuito) if gratuito else None,
        "coupon_hint": (cupom or {}).get("code") or "RITUAL10",
    }
