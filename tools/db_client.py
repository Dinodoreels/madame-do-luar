import hashlib
import os
import secrets
import requests
import bcrypt
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_supabase_headers():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Credenciais do Supabase ausentes no .env.")
    return url, {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None

def _get_count(table: str, query: str = "", timeout: int = 3) -> int:
    """Conta registros via Supabase REST. Retorna 0 se a tabela ainda nao existir."""
    try:
        url, headers = get_supabase_headers()
        endpoint = f"{url}/rest/v1/{table}?select=*"
        if query:
            endpoint += f"&{query}"
        r = requests.get(endpoint, headers={**headers, "Prefer": "count=exact"}, timeout=timeout)
        return int(r.headers.get("content-range", "0/0").split("/")[-1])
    except Exception:
        return 0

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def _money_sum(rows: list[dict]) -> float:
    return round(sum(float(item.get("amount") or item.get("valor") or 0) for item in rows), 2)

def _safe_list(table: str, select: str = "*", filtros: str = "", limit: int = 1000, order: str = None, timeout: int = 6) -> list[dict]:
    try:
        return listar_registros(table, select=select, filtros=filtros, limit=limit, order=order, timeout=timeout)
    except Exception:
        return []

def get_setting(key: str, default=None):
    try:
        rows = listar_registros("settings", select="value", filtros=f"key=eq.{key}", limit=1)
        if not rows:
            return default
        value = rows[0].get("value")
        if value in ("true", "false"):
            return value == "true"
        return value
    except Exception:
        return default

def set_setting(key: str, value, is_secret: bool = False):
    existing = listar_registros("settings", select="setting_id", filtros=f"key=eq.{key}", limit=1)
    payload = {
        "key": key,
        "value": str(value).lower() if isinstance(value, bool) else str(value),
        "is_secret": is_secret,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        return atualizar_registro("settings", "setting_id", existing[0]["setting_id"], payload)
    return criar_registro("settings", payload)

def _rpc(function_name: str, payload: dict) -> dict:
    """Chama uma funcao RPC do Supabase."""
    url, headers = get_supabase_headers()
    r = requests.post(f"{url}/rest/v1/rpc/{function_name}", headers=headers, json=payload, timeout=20)
    data = _safe_json(r)
    if r.status_code >= 400:
        detalhe = data.get("message") if isinstance(data, dict) else r.text
        return {"erro": detalhe or f"RPC {function_name} falhou."}
    return data if isinstance(data, dict) else {"resultado": data}

def _rpc_indisponivel(resultado: dict) -> bool:
    erro = str((resultado or {}).get("erro") or "").lower()
    return any(
        marker in erro
        for marker in (
            "schema cache",
            "could not find the function",
            "function public.",
            "funcao nao encontrada",
            "function not found",
        )
    )

def obter_custo_leitura(tipo: str = "tres_cartas") -> int:
    """Busca custo configurado em settings; usa padrao local se nao existir."""
    defaults = {
        "simples": 25,
        "geral": 25,
        "energia_do_dia": 0,
        "conselho_espiritual": 25,
        "sim_nao": 25,
        "amor": 50,
        "dinheiro": 50,
        "carreira": 50,
        "tres_cartas": 50,
        "personalizada": 100,
        "premium": 250,
    }
    tipo_normalizado = (tipo or "tres_cartas").strip().lower()
    try:
        url, headers = get_supabase_headers()
        key = f"reading_cost_{tipo_normalizado}"
        r = requests.get(f"{url}/rest/v1/settings?key=eq.{key}&select=value&limit=1", headers=headers, timeout=10)
        data = _safe_json(r)
        if isinstance(data, list) and data:
            valor = int(data[0].get("value") or 0)
            if valor >= 0:
                return valor
    except Exception:
        pass
    return defaults.get(tipo_normalizado, 1)

def consumir_creditos(user_id: str, amount: int, reason: str, related_reading_id: str = None) -> dict:
    return _rpc("consume_user_credits", {
        "p_user_id": user_id,
        "p_amount": amount,
        "p_reason": reason,
        "p_related_reading_id": related_reading_id,
    })

def estornar_creditos(user_id: str, amount: int, reason: str, related_reading_id: str = None) -> dict:
    return _rpc("refund_user_credits", {
        "p_user_id": user_id,
        "p_amount": amount,
        "p_reason": reason,
        "p_related_reading_id": related_reading_id,
    })

def comprar_ritual_com_creditos(
    user_id: str,
    ritual_id: str,
    amount: int,
    reason: str,
    coupon_code: str = None,
) -> dict:
    resultado = _rpc("purchase_ritual_with_credits", {
        "p_user_id": user_id,
        "p_ritual_id": ritual_id,
        "p_amount": amount,
        "p_reason": reason,
        "p_coupon_code": coupon_code,
    })
    if "erro" in resultado and _rpc_indisponivel(resultado):
        return {"fallback_required": True, "erro": resultado["erro"]}
    return resultado

def vincular_transacao_credito(transaction_id: str, related_reading_id: str = None, related_payment_id: str = None):
    """Relaciona uma transacao de credito a leitura/pagamento quando o ID nasce depois."""
    if not transaction_id:
        return
    payload = {}
    if related_reading_id:
        payload["related_reading_id"] = related_reading_id
    if related_payment_id:
        payload["related_payment_id"] = related_payment_id
    if not payload:
        return
    try:
        url, headers = get_supabase_headers()
        requests.patch(
            f"{url}/rest/v1/credit_transactions?transaction_id=eq.{transaction_id}",
            headers=headers,
            json=payload,
            timeout=10,
        )
    except Exception:
        pass

def marcar_primeira_tiragem_usada(user_id: str):
    try:
        url, headers = get_supabase_headers()
        requests.patch(
            f"{url}/rest/v1/users?user_id=eq.{user_id}",
            headers=headers,
            json={"primeira_tiragem_gratis": False}
        )
    except Exception:
        pass

def registrar_log(
    event_type: str,
    description: str,
    user_id: str = None,
    admin_id: str = None,
    metadata: dict = None,
    severity: str = "info",
    ip_address: str = None,
    user_agent: str = None,
):
    """Registra auditoria. Falha silenciosamente se a migration ainda nao foi aplicada."""
    try:
        url, headers = get_supabase_headers()
        payload = {
            "event_type": event_type,
            "description": description,
            "user_id": user_id,
            "admin_id": admin_id,
            "metadata": metadata or {},
            "severity": severity,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        requests.post(f"{url}/rest/v1/system_logs", headers=headers, json=payload, timeout=10)
    except Exception:
        pass

def registrar_auditoria(
    action: str,
    entity_type: str = None,
    entity_id: str = None,
    user_id: str = None,
    admin_id: str = None,
    before_data: dict = None,
    after_data: dict = None,
    metadata: dict = None,
    severity: str = "info",
    ip_address: str = None,
    user_agent: str = None,
):
    audit = criar_registro("audit_logs", {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": user_id,
        "admin_id": admin_id,
        "before_data": before_data or {},
        "after_data": after_data or {},
        "metadata": metadata or {},
        "severity": severity,
        "ip_address": ip_address,
        "user_agent": user_agent,
    })
    registrar_log(
        action,
        f"Auditoria: {action}",
        user_id=user_id,
        admin_id=admin_id,
        metadata={"entity_type": entity_type, "entity_id": entity_id, **(metadata or {})},
        severity=severity,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return audit

def criar_alerta_interno(type_: str, title: str, description: str = None, severity: str = "info", user_id: str = None, payment_id: str = None, metadata: dict = None):
    return criar_registro("internal_alerts", {
        "type": type_,
        "title": title,
        "description": description,
        "severity": severity,
        "user_id": user_id,
        "payment_id": payment_id,
        "metadata": metadata or {},
    })

def alerta_aberto_existe(type_: str, title: str, fingerprint: str = None) -> bool:
    filtros = f"type=eq.{type_}&title=eq.{title}&status=in.(open,acknowledged)"
    for alert in _safe_list("internal_alerts", select="alert_id,metadata", filtros=filtros, limit=20):
        if not fingerprint:
            return True
        metadata = alert.get("metadata") or {}
        if metadata.get("fingerprint") == fingerprint:
            return True
    return False

def criar_alerta_unico(type_: str, title: str, description: str = None, severity: str = "info", user_id: str = None, payment_id: str = None, metadata: dict = None):
    metadata = metadata or {}
    fingerprint = metadata.get("fingerprint") or hashlib.sha256(
        json.dumps({
            "type": type_,
            "title": title,
            "user_id": user_id,
            "payment_id": payment_id,
            "metadata": metadata,
        }, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]
    metadata["fingerprint"] = fingerprint
    if alerta_aberto_existe(type_, title, fingerprint):
        return {"skipped": True, "reason": "alerta_aberto_existente", "fingerprint": fingerprint}
    return criar_alerta_interno(type_, title, description, severity, user_id, payment_id, metadata)

def enfileirar_reprocessamento(type_: str, payload: dict, related_payment_id: str = None, related_reading_id: str = None, error_message: str = None):
    return criar_registro("reprocess_queue", {
        "type": type_,
        "payload": payload or {},
        "related_payment_id": related_payment_id,
        "related_reading_id": related_reading_id,
        "error_message": error_message,
    })

def listar_registros(tabela: str, select: str = "*", filtros: str = "", limit: int = 50, order: str = None, timeout: int = 8):
    """Listagem generica para telas admin."""
    url, headers = get_supabase_headers()
    endpoint = f"{url}/rest/v1/{tabela}?select={select}&limit={limit}"
    if filtros:
        endpoint += f"&{filtros}"
    if order:
        endpoint += f"&order={order}"
    r = requests.get(endpoint, headers=headers, timeout=timeout)
    data = _safe_json(r)
    return data if isinstance(data, list) else []

def criar_registro(tabela: str, payload: dict) -> dict:
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    r = requests.post(f"{url}/rest/v1/{tabela}", headers=post_headers, json=payload, timeout=15)
    data = _safe_json(r)
    if r.status_code >= 400:
        detalhe = data.get("message") if isinstance(data, dict) else r.text
        return {"erro": detalhe or f"Nao foi possivel criar registro em {tabela}."}
    return data[0] if isinstance(data, list) and data else {}

def atualizar_registro(tabela: str, id_coluna: str, id_valor: str, payload: dict) -> dict:
    url, headers = get_supabase_headers()
    patch_headers = dict(headers)
    patch_headers["Prefer"] = "return=representation"
    r = requests.patch(
        f"{url}/rest/v1/{tabela}?{id_coluna}=eq.{id_valor}",
        headers=patch_headers,
        json=payload,
        timeout=15,
    )
    data = _safe_json(r)
    if r.status_code >= 400:
        detalhe = data.get("message") if isinstance(data, dict) else r.text
        return {"erro": detalhe or f"Nao foi possivel atualizar registro em {tabela}."}
    if not isinstance(data, list) or not data:
        return {"erro": "Registro nao encontrado."}
    return data[0]

def registrar_mudanca_plano(user_id: str, new_plan_id: str, admin_id: str = None, reason: str = None):
    usuario = get_user_by_id(user_id)
    if not usuario:
        return {"erro": "Usuario nao encontrado."}

    old_plan_id = usuario.get("plan_id")
    atualizado = atualizar_registro("users", "user_id", user_id, {"plan_id": new_plan_id})
    if "erro" in atualizado:
        return atualizado

    historico = criar_registro("plan_change_history", {
        "user_id": user_id,
        "old_plan_id": old_plan_id,
        "new_plan_id": new_plan_id,
        "changed_by_admin_id": admin_id,
        "reason": reason,
        "metadata": {"old_plan_id": old_plan_id, "new_plan_id": new_plan_id},
    })

    registrar_log(
        event_type="PLAN_CHANGED",
        description="Plano do usuario alterado.",
        user_id=user_id,
        admin_id=admin_id,
        metadata={"old_plan_id": old_plan_id, "new_plan_id": new_plan_id, "reason": reason},
    )
    if atualizado:
        atualizado.pop("senha_hash", None)
    return {"usuario": atualizado, "historico": historico}

def buscar_por_id(tabela: str, id_coluna: str, id_valor: str, select: str = "*") -> dict:
    rows = listar_registros(tabela, select=select, filtros=f"{id_coluna}=eq.{id_valor}", limit=1)
    return rows[0] if rows else None

def normalizar_codigo_cupom(codigo: str) -> str:
    return "".join(str(codigo or "").strip().upper().split())

def calcular_desconto_cupom(coupon: dict, amount: float, product_type: str = None) -> dict:
    if not coupon:
        return {"erro": "Cupom nao encontrado."}
    if coupon.get("status") != "active":
        return {"erro": "Cupom inativo."}
    if coupon.get("max_uses") is not None and int(coupon.get("used_count") or 0) >= int(coupon.get("max_uses") or 0):
        return {"erro": "Cupom esgotado."}
    if float(amount or 0) < float(coupon.get("minimum_amount") or 0):
        return {"erro": "Valor minimo do cupom nao atingido."}
    applies_to = coupon.get("applies_to")
    if applies_to and applies_to not in ("all", product_type):
        return {"erro": "Cupom nao se aplica a este produto."}

    now = datetime.now(timezone.utc)
    for field, operator in (("starts_at", "before"), ("expires_at", "after")):
        value = coupon.get(field)
        if not value:
            continue
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if operator == "before" and now < dt:
                return {"erro": "Cupom ainda nao esta ativo."}
            if operator == "after" and now > dt:
                return {"erro": "Cupom expirado."}
        except Exception:
            pass

    discount_type = coupon.get("discount_type")
    discount_value = float(coupon.get("discount_value") or 0)
    if discount_type == "percent":
        discount = float(amount or 0) * min(discount_value, 100) / 100
    elif discount_type == "fixed":
        discount = discount_value
    else:
        return {"erro": "Tipo de cupom invalido."}
    discount = round(min(max(discount, 0), float(amount or 0)), 2)
    return {"discount_amount": discount, "final_amount": round(float(amount or 0) - discount, 2)}

def aplicar_cupom_produto(produto: dict, coupon_code: str = None) -> dict:
    if not coupon_code:
        return produto
    codigo = normalizar_codigo_cupom(coupon_code)
    coupon = buscar_por_id("coupons", "code", codigo)
    calculo = calcular_desconto_cupom(coupon, float(produto.get("amount") or 0), produto.get("product_type"))
    if "erro" in calculo:
        return calculo
    produto = dict(produto)
    produto["original_amount"] = float(produto.get("amount") or 0)
    produto["amount"] = calculo["final_amount"]
    produto["discount_amount"] = calculo["discount_amount"]
    produto["coupon_code"] = codigo
    produto["coupon_id"] = coupon.get("coupon_id")
    return produto

def calcular_produto_pagamento(product_type: str, product_id: str) -> dict:
    if product_type == "package":
        pacote = buscar_por_id("credit_packages", "package_id", product_id)
        if not pacote:
            return {"erro": "Pacote de creditos nao encontrado."}
        if pacote.get("status") != "active":
            return {"erro": "Pacote de creditos inativo."}
        credits = int(pacote.get("credits") or 0) + int(pacote.get("bonus_credits") or 0)
        return {
            "product_type": "package",
            "package_id": pacote.get("package_id"),
            "product_name": pacote.get("name"),
            "amount": float(pacote.get("price") or 0),
            "credits_to_release": credits,
            "validity_days": pacote.get("validity_days"),
        }

    if product_type == "plan":
        plano = buscar_por_id("plans", "plan_id", product_id)
        if not plano:
            return {"erro": "Plano nao encontrado."}
        if plano.get("status") != "active":
            return {"erro": "Plano inativo."}
        return {
            "product_type": "plan",
            "plan_id": plano.get("plan_id"),
            "product_name": plano.get("name"),
            "amount": float(plano.get("price") or 0),
            "credits_to_release": int(plano.get("credits") or 0),
            "duration_days": plano.get("duration_days"),
        }

    if product_type == "ritual":
        ritual = buscar_por_id("rituals", "ritual_id", product_id)
        if not ritual:
            return {"erro": "Ritual nao encontrado."}
        if not ritual.get("ativo", True):
            return {"erro": "Ritual inativo."}
        return {
            "product_type": "ritual",
            "ritual_id": ritual.get("ritual_id"),
            "product_name": ritual.get("nome"),
            "amount": float(ritual.get("preco") or 0),
            "credits_to_release": 0,
            "ritual": ritual,
        }

    return {"erro": "Tipo de produto invalido."}

def registrar_tentativa_pagamento_pix(
    user_id: str,
    produto: dict,
    gateway: str,
    transaction_id: str,
    expires_at: str,
    qr_code_url: str = None,
    pix_copy_paste: str = None,
    checkout_url: str = None,
    gateway_payload: dict = None,
) -> dict:
    payload = {
        "user_id": user_id,
        "plan_id": produto.get("plan_id"),
        "package_id": produto.get("package_id"),
        "product_type": produto.get("product_type"),
        "product_name": produto.get("product_name"),
        "valor": produto.get("amount"),
        "amount": produto.get("amount"),
        "original_amount": produto.get("original_amount") or produto.get("amount"),
        "discount_amount": produto.get("discount_amount") or 0,
        "coupon_code": produto.get("coupon_code"),
        "status": "pending",
        "tipo": "assinatura" if produto.get("product_type") == "plan" else ("ritual" if produto.get("product_type") == "ritual" else "leitura"),
        "method": "PIX",
        "gateway": gateway,
        "transaction_id": transaction_id,
        "qr_code_url": qr_code_url,
        "pix_copy_paste": pix_copy_paste,
        "checkout_url": checkout_url,
        "expires_at": expires_at,
        "credits_to_release": produto.get("credits_to_release", 0),
        "gateway_payload": {
            **(gateway_payload or {}),
            "original_amount": produto.get("original_amount") or produto.get("amount"),
            "discount_amount": produto.get("discount_amount") or 0,
            "coupon_code": produto.get("coupon_code"),
        },
        "gateway_ref": transaction_id,
    }
    created = criar_registro("payments", payload)
    if "erro" in created and any(field in str(created["erro"]) for field in ("coupon_code", "original_amount", "discount_amount")):
        for field in ("coupon_code", "original_amount", "discount_amount"):
            payload.pop(field, None)
        created = criar_registro("payments", payload)
    return created

def registrar_uso_cupom(coupon_code: str, payment_id: str = None, user_id: str = None) -> dict:
    """Incrementa uso de cupom quando a venda e confirmada."""
    codigo = normalizar_codigo_cupom(coupon_code)
    if not codigo:
        return {"skipped": True, "reason": "sem_cupom"}
    coupon = buscar_por_id("coupons", "code", codigo)
    if not coupon:
        return {"skipped": True, "reason": "cupom_nao_encontrado", "coupon_code": codigo}
    usado = int(coupon.get("used_count") or 0) + 1
    atualizado = atualizar_registro("coupons", "coupon_id", coupon["coupon_id"], {
        "used_count": usado,
        "updated_at": _now_iso(),
    })
    if "erro" not in atualizado:
        registrar_log(
            "COUPON_USED",
            "Cupom contabilizado em pagamento aprovado.",
            user_id=user_id,
            metadata={"coupon_code": codigo, "payment_id": payment_id, "used_count": usado},
        )
    return atualizado

def registrar_webhook_pagamento(event_id: str, payload: dict, gateway: str, event_type: str, transaction_id: str = None, payment_id: str = None) -> dict:
    evento = criar_registro("payment_webhook_events", {
        "event_id": event_id,
        "payment_id": payment_id,
        "gateway": gateway,
        "event_type": event_type,
        "transaction_id": transaction_id,
        "payload": payload,
    })
    if "erro" in evento and "duplicate" in str(evento["erro"]).lower():
        return {"duplicado": True, "event_id": event_id}
    return evento

def buscar_pagamento_por_transacao(transaction_id: str) -> dict:
    return buscar_por_id("payments", "transaction_id", transaction_id)

def liberar_creditos_pagamento(payment: dict, admin_id: str = None, reason: str = "Pagamento PIX aprovado") -> dict:
    if not payment:
        return {"erro": "Pagamento nao encontrado."}
    if payment.get("credits_released"):
        return {"ok": True, "ja_liberado": True, "payment_id": payment.get("payment_id")}

    credits = int(payment.get("credits_to_release") or 0)
    if credits <= 0:
        return {"ok": True, "sem_creditos": True, "payment_id": payment.get("payment_id")}

    expires_at = None
    validade = None
    if payment.get("package_id"):
        pacote = buscar_por_id("credit_packages", "package_id", payment.get("package_id"))
        validade = pacote.get("validity_days") if pacote else None
    if validade:
        from datetime import datetime, timezone, timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(days=int(validade))).isoformat()

    resultado = ajustar_creditos(
        user_id=payment.get("user_id"),
        amount=credits,
        tipo="add",
        reason=reason,
        admin_id=admin_id,
        related_payment_id=payment.get("payment_id"),
        expires_at=expires_at,
    )
    if "erro" in resultado:
        return resultado

    atualizar_registro("payments", "payment_id", payment.get("payment_id"), {
        "credits_released": True,
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    })
    return resultado

def aprovar_pagamento_pix(payment_id: str, webhook_payload: dict = None, admin_id: str = None, manual: bool = False) -> dict:
    from datetime import datetime, timezone
    payment = buscar_por_id("payments", "payment_id", payment_id)
    if not payment:
        return {"erro": "Pagamento nao encontrado."}

    rpc_result = _rpc("approve_payment_once", {
        "p_payment_id": payment_id,
        "p_webhook_payload": webhook_payload or payment.get("webhook_payload") or {},
        "p_admin_id": admin_id,
        "p_manual": manual,
        "p_reason": "Conciliacao manual de PIX" if manual else "Pagamento PIX aprovado automaticamente",
    })
    if "erro" not in rpc_result:
        atualizado = buscar_por_id("payments", "payment_id", payment_id) or payment
        gateway_payload = atualizado.get("gateway_payload") if isinstance(atualizado.get("gateway_payload"), dict) else {}
        metadata = gateway_payload.get("metadata") if isinstance(gateway_payload.get("metadata"), dict) else {}
        coupon_code = atualizado.get("coupon_code") or metadata.get("coupon_code") or gateway_payload.get("coupon_code")
        cupom = {"skipped": True, "reason": "pagamento_ja_processado"}
        if coupon_code and not rpc_result.get("ja_liberado"):
            cupom = registrar_uso_cupom(coupon_code, payment_id=payment_id, user_id=atualizado.get("user_id"))

        if atualizado.get("product_type") == "ritual":
            compra = buscar_por_id("ritual_purchases", "payment_id", payment_id)
            if compra:
                compra_atualizada = atualizar_registro("ritual_purchases", "purchase_id", compra["purchase_id"], {
                    "status": "approved",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                if "erro" in compra_atualizada:
                    atualizar_registro("ritual_purchases", "purchase_id", compra["purchase_id"], {"status": "approved"})

        registrar_log(
            event_type="PIX_APPROVED",
            description="Pagamento PIX aprovado e creditos liberados de forma idempotente.",
            user_id=atualizado.get("user_id"),
            admin_id=admin_id,
            metadata={"payment_id": payment_id, "manual": manual, "creditos": rpc_result, "idempotent": True},
        )
        return {"pagamento": atualizado, "creditos": rpc_result, "cupom": cupom}

    if not _rpc_indisponivel(rpc_result):
        return rpc_result

    if payment.get("status") == "approved" and payment.get("credits_released"):
        return {"pagamento": payment, "creditos": {"ja_liberado": True}}

    atualizado = atualizar_registro("payments", "payment_id", payment_id, {
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "webhook_payload": webhook_payload or payment.get("webhook_payload"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    if "erro" in atualizado:
        return atualizado

    creditos = liberar_creditos_pagamento(
        atualizado,
        admin_id=admin_id,
        reason="Conciliacao manual de PIX" if manual else "Pagamento PIX aprovado automaticamente",
    )

    gateway_payload = atualizado.get("gateway_payload") if isinstance(atualizado.get("gateway_payload"), dict) else {}
    metadata = gateway_payload.get("metadata") if isinstance(gateway_payload.get("metadata"), dict) else {}
    coupon_code = atualizado.get("coupon_code") or metadata.get("coupon_code") or gateway_payload.get("coupon_code")
    cupom = registrar_uso_cupom(coupon_code, payment_id=payment_id, user_id=atualizado.get("user_id")) if coupon_code else {"skipped": True}

    if atualizado.get("product_type") == "ritual":
        compra = buscar_por_id("ritual_purchases", "payment_id", payment_id)
        if compra:
            compra_atualizada = atualizar_registro("ritual_purchases", "purchase_id", compra["purchase_id"], {
                "status": "approved",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            if "erro" in compra_atualizada:
                atualizar_registro("ritual_purchases", "purchase_id", compra["purchase_id"], {"status": "approved"})

    registrar_log(
        event_type="PIX_APPROVED",
        description="Pagamento PIX aprovado e creditos liberados.",
        user_id=atualizado.get("user_id"),
        admin_id=admin_id,
        metadata={"payment_id": payment_id, "manual": manual, "creditos": creditos},
    )
    return {"pagamento": atualizado, "creditos": creditos, "cupom": cupom}

def marcar_pagamentos_pix_abandonados() -> dict:
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc).isoformat()
    pendentes = listar_registros(
        "payments",
        select="*",
        filtros=f"status=eq.pending&expires_at=lt.{agora}",
        limit=500,
    )
    marcados = []
    for payment in pendentes:
        atualizado = atualizar_registro("payments", "payment_id", payment["payment_id"], {
            "status": "abandoned",
            "abandoned_at": agora,
            "updated_at": agora,
        })
        if "erro" not in atualizado:
            marcados.append(atualizado)
            registrar_log(
                event_type="PIX_EXPIRED",
                description="PIX pendente marcado como abandonado.",
                user_id=payment.get("user_id"),
                metadata={"payment_id": payment.get("payment_id"), "transaction_id": payment.get("transaction_id")},
                severity="warning",
            )
    return {"marcados": len(marcados), "pagamentos": marcados}

def calcular_score_engajamento(usuario: dict) -> dict:
    user_id = usuario.get("user_id")
    leituras = _get_count("questions", f"user_id=eq.{user_id}")
    pagamentos = listar_registros("payments", select="status,amount,valor", filtros=f"user_id=eq.{user_id}", limit=200)
    aprovados = [p for p in pagamentos if p.get("status") == "approved"]
    pendentes = [p for p in pagamentos if p.get("status") == "pending"]
    receita = sum(float(p.get("amount") or p.get("valor") or 0) for p in aprovados)
    credits = int(usuario.get("credits_balance") or 0)
    last_login = usuario.get("last_login_at")

    recency = 0
    try:
        if last_login:
            dt = datetime.fromisoformat(str(last_login).replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days
            recency = max(0, 25 - min(days, 25))
    except Exception:
        pass

    score = min(100, (leituras * 8) + (len(aprovados) * 18) + min(int(receita // 10), 20) + recency + (10 if pendentes else 0))
    reasons = []
    if leituras >= 2:
        reasons.append("fez multiplas leituras")
    if aprovados:
        reasons.append("ja comprou")
    if pendentes:
        reasons.append("tem PIX pendente")
    if credits == 0 and leituras > 0:
        reasons.append("consumiu todos os creditos")
    return {
        "user_id": user_id,
        "nome": usuario.get("nome"),
        "email": usuario.get("email"),
        "score": score,
        "leituras": leituras,
        "pagamentos_aprovados": len(aprovados),
        "pagamentos_pendentes": len(pendentes),
        "receita": receita,
        "credits_balance": credits,
        "hot": score >= 45 or bool(pendentes),
        "reasons": reasons,
    }

def relatorio_engajamento(limit: int = 100) -> dict:
    usuarios = listar_registros(
        "users",
        select="user_id,nome,email,credits_balance,last_login_at,criado_em",
        limit=limit,
        order="criado_em.desc",
    )
    scores = [calcular_score_engajamento(u) for u in usuarios]
    scores.sort(key=lambda item: item["score"], reverse=True)
    return {"usuarios": scores}

def usuarios_quentes(limit: int = 100) -> dict:
    scores = relatorio_engajamento(limit)["usuarios"]
    hot = [u for u in scores if u["hot"]]
    return {"usuarios": hot, "total": len(hot)}

def relatorio_financeiro() -> dict:
    pagamentos = listar_registros("payments", select="*", limit=1000, order="created_at.desc")
    aprovados = [p for p in pagamentos if p.get("status") == "approved"]
    pendentes = [p for p in pagamentos if p.get("status") == "pending"]
    abandonados = [p for p in pagamentos if p.get("status") in ("abandoned", "expired")]
    receita = sum(float(p.get("amount") or p.get("valor") or 0) for p in aprovados)
    ticket = receita / len(aprovados) if aprovados else 0
    por_produto = {}
    por_tipo = {}
    for p in aprovados:
        nome = p.get("product_name") or p.get("tipo") or "produto"
        tipo = p.get("product_type") or p.get("tipo") or "produto"
        por_produto.setdefault(nome, {"receita": 0, "vendas": 0, "tipo": tipo})
        por_produto[nome]["receita"] += float(p.get("amount") or p.get("valor") or 0)
        por_produto[nome]["vendas"] += 1
        por_tipo.setdefault(tipo, {"receita": 0, "vendas": 0})
        por_tipo[tipo]["receita"] += float(p.get("amount") or p.get("valor") or 0)
        por_tipo[tipo]["vendas"] += 1
    return {
        "receita_total": receita,
        "ticket_medio": ticket,
        "pagamentos_aprovados": len(aprovados),
        "pagamentos_pendentes": len(pendentes),
        "pagamentos_abandonados": len(abandonados),
        "produtos": por_produto,
        "tipos": por_tipo,
    }

def relatorio_ia() -> dict:
    readings = listar_registros("readings", select="*", limit=1000, order="criado_em.desc")
    total_tokens = sum(int(r.get("tokens_used") or 0) for r in readings)
    custo = sum(float(r.get("estimated_cost") or 0) for r in readings)
    erros = [r for r in readings if r.get("status") == "erro"]
    por_modelo = {}
    for r in readings:
        model = r.get("model") or "desconhecido"
        por_modelo.setdefault(model, {"leituras": 0, "tokens": 0, "custo": 0, "erros": 0})
        por_modelo[model]["leituras"] += 1
        por_modelo[model]["tokens"] += int(r.get("tokens_used") or 0)
        por_modelo[model]["custo"] += float(r.get("estimated_cost") or 0)
        por_modelo[model]["erros"] += 1 if r.get("status") == "erro" else 0
    return {
        "leituras_total": len(readings),
        "leituras_com_erro": len(erros),
        "tokens_total": total_tokens,
        "custo_estimado": custo,
        "por_modelo": por_modelo,
    }

def metricas_conversao() -> dict:
    usuarios = _safe_list("users", select="user_id,criado_em,assinante,plan_id", limit=5000)
    pagamentos = _safe_list("payments", select="user_id,status,amount,valor,created_at,product_type", limit=5000, order="created_at.desc")
    leituras = _safe_list("readings", select="user_id,status,created_at,criado_em", limit=5000, order="criado_em.desc")
    perguntas = _safe_list("questions", select="user_id,created_at,criado_em", limit=5000, order="criado_em.desc")
    aprovados = [p for p in pagamentos if p.get("status") == "approved"]
    pendentes = [p for p in pagamentos if p.get("status") == "pending"]
    abandonados = [p for p in pagamentos if p.get("status") in ("abandoned", "expired", "cancelled", "refused")]
    compradores = {p.get("user_id") for p in aprovados if p.get("user_id")}
    leitores = {r.get("user_id") for r in leituras if r.get("user_id")}
    leitores.update(q.get("user_id") for q in perguntas if q.get("user_id"))
    total_usuarios = len(usuarios)
    total_checkouts = len(pagamentos)
    return {
        "usuarios_total": total_usuarios,
        "usuarios_com_leitura": len(leitores),
        "compradores": len(compradores),
        "checkouts_total": total_checkouts,
        "checkouts_aprovados": len(aprovados),
        "checkouts_pendentes": len(pendentes),
        "checkouts_abandonados": len(abandonados),
        "taxa_usuario_para_leitura": round((len(leitores) / total_usuarios) * 100, 2) if total_usuarios else 0,
        "taxa_usuario_para_compra": round((len(compradores) / total_usuarios) * 100, 2) if total_usuarios else 0,
        "taxa_checkout_aprovado": round((len(aprovados) / total_checkouts) * 100, 2) if total_checkouts else 0,
        "taxa_checkout_abandonado": round((len(abandonados) / total_checkouts) * 100, 2) if total_checkouts else 0,
    }

def metricas_retencao() -> dict:
    now = datetime.now(timezone.utc)
    cutoff_7 = now - timedelta(days=7)
    cutoff_30 = now - timedelta(days=30)
    usuarios = _safe_list("users", select="user_id,criado_em,last_login_at,updated_at", limit=5000)
    leituras = _safe_list("readings", select="user_id,created_at,criado_em,status", limit=5000, order="criado_em.desc")
    perguntas = _safe_list("questions", select="user_id,created_at,criado_em", limit=5000, order="criado_em.desc")
    mensagens = _safe_list("message_events", select="user_id,status,created_at,enviado_em", limit=5000, order="created_at.desc")
    leitura_por_usuario = {}
    ativos_7 = set()
    ativos_30 = set()

    def touch(user_id, value):
        when = _parse_dt(value)
        if not user_id or not when:
            return
        if when >= cutoff_7:
            ativos_7.add(user_id)
        if when >= cutoff_30:
            ativos_30.add(user_id)

    for user in usuarios:
        touch(user.get("user_id"), user.get("last_login_at") or user.get("updated_at") or user.get("criado_em"))
    for reading in leituras:
        uid = reading.get("user_id")
        if uid:
            leitura_por_usuario[uid] = leitura_por_usuario.get(uid, 0) + 1
        touch(uid, reading.get("created_at") or reading.get("criado_em"))
    for question in perguntas:
        uid = question.get("user_id")
        if uid:
            leitura_por_usuario[uid] = leitura_por_usuario.get(uid, 0) + 1
        touch(uid, question.get("created_at") or question.get("criado_em"))
    for message in mensagens:
        touch(message.get("user_id"), message.get("enviado_em") or message.get("created_at"))

    recorrentes = [uid for uid, total in leitura_por_usuario.items() if total > 1]
    total_usuarios = len(usuarios)
    return {
        "usuarios_total": total_usuarios,
        "ativos_7_dias": len(ativos_7),
        "ativos_30_dias": len(ativos_30),
        "usuarios_recorrentes": len(recorrentes),
        "taxa_ativo_7_dias": round((len(ativos_7) / total_usuarios) * 100, 2) if total_usuarios else 0,
        "taxa_ativo_30_dias": round((len(ativos_30) / total_usuarios) * 100, 2) if total_usuarios else 0,
        "taxa_recorrencia_leitura": round((len(recorrentes) / total_usuarios) * 100, 2) if total_usuarios else 0,
        "risco_inatividade": max(total_usuarios - len(ativos_30), 0),
    }

def metricas_receita() -> dict:
    now = datetime.now(timezone.utc)
    pagamentos = _safe_list("payments", select="user_id,status,amount,valor,created_at,product_name,product_type", limit=5000, order="created_at.desc")
    assinaturas = _safe_list("subscriptions", select="user_id,status,plano,valor,created_at,updated_at,renovacao", limit=5000, order="created_at.desc")
    aprovados = [p for p in pagamentos if p.get("status") == "approved"]
    assinaturas_ativas = [s for s in assinaturas if s.get("status") in ("ativo", "active")]
    assinaturas_canceladas = [s for s in assinaturas if s.get("status") in ("cancelado", "cancelled", "canceled")]

    def in_days(payment, days: int) -> bool:
        when = _parse_dt(payment.get("created_at"))
        return bool(when and when >= now - timedelta(days=days))

    receita_total = _money_sum(aprovados)
    receita_7 = _money_sum([p for p in aprovados if in_days(p, 7)])
    receita_30 = _money_sum([p for p in aprovados if in_days(p, 30)])
    compradores = {p.get("user_id") for p in aprovados if p.get("user_id")}
    receita_por_usuario = {}
    por_tipo = {}
    for payment in aprovados:
        tipo = payment.get("product_type") or payment.get("tipo") or "produto"
        user_id = payment.get("user_id")
        if user_id:
            receita_por_usuario[user_id] = round(receita_por_usuario.get(user_id, 0) + float(payment.get("amount") or payment.get("valor") or 0), 2)
        por_tipo.setdefault(tipo, {"receita": 0, "vendas": 0})
        por_tipo[tipo]["receita"] = round(por_tipo[tipo]["receita"] + float(payment.get("amount") or payment.get("valor") or 0), 2)
        por_tipo[tipo]["vendas"] += 1
    total_assinaturas_encerradas = len(assinaturas_ativas) + len(assinaturas_canceladas)
    churn_rate = round((len(assinaturas_canceladas) / total_assinaturas_encerradas) * 100, 2) if total_assinaturas_encerradas else 0
    mrr_estimado = 0.0
    for sub in assinaturas_ativas:
        valor = float(sub.get("valor") or 0)
        if not valor:
            valor = 397 / 12 if str(sub.get("plano") or "").lower() == "anual" else 49.90
        mrr_estimado += valor
    return {
        "receita_total": receita_total,
        "receita_7_dias": receita_7,
        "receita_30_dias": receita_30,
        "pagamentos_aprovados": len(aprovados),
        "compradores_unicos": len(compradores),
        "ticket_medio": round(receita_total / len(aprovados), 2) if aprovados else 0,
        "ltv_medio": round(receita_total / len(compradores), 2) if compradores else 0,
        "mrr_estimado": round(mrr_estimado, 2),
        "assinaturas_ativas": len(assinaturas_ativas),
        "assinaturas_canceladas": len(assinaturas_canceladas),
        "churn_rate": churn_rate,
        "receita_por_usuario_top": sorted(
            [{"user_id": uid, "receita": valor} for uid, valor in receita_por_usuario.items()],
            key=lambda item: item["receita"],
            reverse=True,
        )[:20],
        "receita_por_tipo": por_tipo,
    }

def health_detalhado() -> dict:
    started = datetime.now(timezone.utc)
    checks = {}

    try:
        url, headers = get_supabase_headers()
        before = datetime.now(timezone.utc)
        response = requests.get(f"{url}/rest/v1/users?select=user_id&limit=1", headers=headers, timeout=4)
        latency = int((datetime.now(timezone.utc) - before).total_seconds() * 1000)
        checks["supabase"] = {
            "status": "ok" if response.status_code < 400 else "error",
            "latency_ms": latency,
            "http_status": response.status_code,
        }
    except Exception as exc:
        checks["supabase"] = {"status": "error", "error": str(exc)[:220]}

    checks["ai"] = {
        "status": "ok" if (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")) else "missing_config",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "errors_recent": _get_count("readings", "status=eq.erro"),
    }
    checks["payments"] = {
        "status": "ok" if os.getenv("MERCADO_PAGO_ACCESS_TOKEN") else "missing_config",
        "mercado_pago_configured": bool(os.getenv("MERCADO_PAGO_ACCESS_TOKEN")),
        "webhook_secret_configured": bool(os.getenv("MERCADO_PAGO_WEBHOOK_SECRET")),
        "pending": _get_count("payments", "status=eq.pending"),
        "errors": _get_count("payments", "status=in.(error,failed,refused)"),
    }
    try:
        from notificacoes import whatsapp_diagnostico_config
        whatsapp_diag = whatsapp_diagnostico_config()
    except Exception as exc:
        whatsapp_diag = {"configured": False, "provider": os.getenv("WHATSAPP_PROVIDER", "uazapi"), "error": str(exc)[:180]}

    smtp_ok = bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))
    whatsapp_ok = bool(whatsapp_diag.get("configured"))
    checks["notifications"] = {
        "status": "ok" if smtp_ok and whatsapp_ok else "degraded",
        "smtp_configured": smtp_ok,
        "whatsapp_configured": whatsapp_ok,
        "whatsapp_provider": whatsapp_diag.get("provider"),
        "whatsapp_missing": whatsapp_diag.get("required_missing") or [],
        "whatsapp_health_endpoint": whatsapp_diag.get("health_endpoint"),
        "pending": _get_count("message_events", "status=eq.pending"),
        "failed": _get_count("message_events", "status=eq.failed"),
        "failed_provider_logs": _get_count("notification_logs", "status=eq.failed"),
    }
    checks["logs"] = {
        "api_errors": _get_count("system_logs", "event_type=eq.API_ERROR"),
        "critical": _get_count("system_logs", "severity=eq.critical"),
        "open_alerts": _get_count("internal_alerts", "status=eq.open"),
    }

    status = "ok"
    if checks["supabase"]["status"] == "error":
        status = "down"
    elif any(item.get("status") in ("error", "missing_config", "degraded") for item in checks.values() if isinstance(item, dict)):
        status = "degraded"

    return {
        "status": status,
        "environment": os.getenv("APP_ENV", "development"),
        "checked_at": _now_iso(),
        "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        "checks": checks,
    }

def painel_status_operacional() -> dict:
    def safe_call(name: str, fn, fallback):
        try:
            return name, fn()
        except Exception:
            return name, fallback

    specs = {
        "health": (health_detalhado, {}),
        "metricas": (resumo_admin, {}),
        "conversao": (metricas_conversao, {}),
        "retencao": (metricas_retencao, {}),
        "receita": (metricas_receita, {}),
        "financeiro": (relatorio_financeiro, {}),
        "ia": (relatorio_ia, {}),
        "alertas_abertos": (lambda: _safe_list("internal_alerts", select="*", filtros="status=eq.open", limit=50, order="created_at.desc"), []),
        "erros_recentes": (lambda: _safe_list("system_logs", select="*", filtros="severity=in.(error,critical)", limit=50, order="created_at.desc"), []),
        "mensagens_pendentes": (lambda: _safe_list("message_events", select="*", filtros="status=eq.pending", limit=50, order="agendado_para.asc"), []),
    }
    resultado = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(safe_call, name, fn, fallback): name
            for name, (fn, fallback) in specs.items()
        }
        for future in as_completed(futures):
            name, value = future.result()
            resultado[name] = value
    return resultado

def gerar_alertas_operacionais() -> dict:
    criados = []
    for payment in listar_registros("payments", select="*", filtros="status=eq.pending", limit=200, order="created_at.desc"):
        try:
            expires = datetime.fromisoformat(str(payment.get("expires_at")).replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                criados.append(criar_alerta_unico(
                    "pix_abandoned",
                    "PIX pendente vencido",
                    "Pagamento PIX ficou pendente apos vencimento.",
                    "warning",
                    user_id=payment.get("user_id"),
                    payment_id=payment.get("payment_id"),
                    metadata={"transaction_id": payment.get("transaction_id"), "fingerprint": f"pix:{payment.get('payment_id')}"},
                ))
        except Exception:
            pass

    for log in _safe_list("system_logs", select="*", filtros="severity=in.(error,critical)", limit=80, order="created_at.desc"):
        event_type = str(log.get("event_type") or "")
        if event_type in ("API_ERROR", "READING_FAILED", "PAYMENT_ERROR", "NOTIFICATION_ERROR") or "WEBHOOK" in event_type or "PAYMENT" in event_type:
            alert_type = "system_error"
            if "WEBHOOK" in event_type:
                alert_type = "webhook_failure"
            elif "READING" in event_type or "AI" in event_type:
                alert_type = "ai_error"
            elif "PAYMENT" in event_type:
                alert_type = "payment_error"
            elif "NOTIFICATION" in event_type:
                alert_type = "notification_error"
            criados.append(criar_alerta_unico(
                alert_type,
                f"Erro operacional: {log.get('event_type')}",
                log.get("description"),
                log.get("severity") or "error",
                user_id=log.get("user_id"),
                metadata={"log_id": log.get("log_id"), "fingerprint": f"log:{log.get('log_id')}"},
            ))

    webhook_failures = _safe_list(
        "payment_webhook_events",
        select="event_id,gateway,event_type,transaction_id,payment_id,created_at,processed,error_message",
        filtros="processed=eq.false",
        limit=50,
        order="created_at.desc",
    )
    for event in webhook_failures:
        criados.append(criar_alerta_unico(
            "webhook_failure",
            "Webhook de pagamento nao processado",
            event.get("error_message") or "Evento de webhook recebido mas ainda nao processado.",
            "critical",
            payment_id=event.get("payment_id"),
            metadata={"event_id": event.get("event_id"), "gateway": event.get("gateway"), "fingerprint": f"webhook:{event.get('event_id')}"},
        ))

    failed_notifications = _safe_list("notification_logs", select="log_id,user_id,channel,type,error_message,created_at", filtros="status=eq.failed", limit=50, order="created_at.desc")
    for item in failed_notifications:
        criados.append(criar_alerta_unico(
            "notification_error",
            "Falha de notificacao",
            item.get("error_message") or "Envio de notificacao falhou.",
            "warning",
            user_id=item.get("user_id"),
            metadata={"log_id": item.get("log_id"), "channel": item.get("channel"), "fingerprint": f"notification:{item.get('log_id')}"},
        ))

    pending_messages = _safe_list("message_events", select="message_id,user_id,tipo,canal,agendado_para,attempts", filtros="status=eq.pending", limit=300, order="agendado_para.asc")
    overdue = []
    now = datetime.now(timezone.utc)
    for item in pending_messages:
        scheduled = _parse_dt(item.get("agendado_para"))
        if scheduled and scheduled < now - timedelta(minutes=30):
            overdue.append(item)
    if len(pending_messages) >= int(os.getenv("PENDING_MESSAGES_ALERT_THRESHOLD", "20")) or overdue:
        criados.append(criar_alerta_unico(
            "pending_notifications",
            "Mensagens pendentes acumuladas",
            f"Existem {len(pending_messages)} mensagens pendentes; {len(overdue)} estao atrasadas ha mais de 30 minutos.",
            "warning" if len(overdue) < 10 else "critical",
            metadata={
                "pending_total": len(pending_messages),
                "overdue_total": len(overdue),
                "fingerprint": f"pending_messages:{datetime.now(timezone.utc).date().isoformat()}",
            },
        ))

    health = health_detalhado()
    if health["status"] in ("degraded", "down"):
        criados.append(criar_alerta_unico(
            "health_degraded",
            "Health check degradado",
            f"Status atual: {health['status']}.",
            "critical" if health["status"] == "down" else "warning",
            metadata={"checks": health.get("checks"), "fingerprint": f"health:{health['status']}:{datetime.now(timezone.utc).date().isoformat()}"},
        ))

    return {"alertas_criados": len([c for c in criados if "erro" not in c and not c.get("skipped")]), "resultados": criados}

def rotina_diaria_verificacao() -> dict:
    status = painel_status_operacional()
    alerts = gerar_alertas_operacionais()
    resultado = {
        "checked_at": _now_iso(),
        "health_status": status["health"]["status"],
        "alertas_criados": alerts["alertas_criados"],
        "conversao": status["conversao"],
        "retencao": status["retencao"],
        "receita": status["receita"],
        "pendencias": {
            "alertas_abertos": len(status["alertas_abertos"]),
            "erros_recentes": len(status["erros_recentes"]),
            "mensagens_pendentes": len(status["mensagens_pendentes"]),
        },
    }
    registrar_log(
        "DAILY_OPERATION_CHECK",
        "Rotina diaria de verificacao operacional executada.",
        metadata=resultado,
        severity="warning" if status["health"]["status"] != "ok" or alerts["alertas_criados"] else "info",
    )
    return {"status": status, "alertas": alerts, "resultado": resultado}

def resumo_admin():
    """Metricas iniciais do painel admin."""
    from datetime import date
    hoje = str(date.today())
    metric_specs = {
        "usuarios_total": ("users", ""),
        "novos_usuarios_hoje": ("users", f"criado_em=gte.{hoje}"),
        "assinantes": ("users", "assinante=eq.true"),
        "leituras_total": ("readings", ""),
        "leituras_hoje": ("readings", f"criado_em=gte.{hoje}"),
        "pagamentos_aprovados": ("payments", "status=eq.approved"),
        "pagamentos_pendentes": ("payments", "status=eq.pending"),
        "mensagens_pendentes": ("message_events", "status=eq.pending"),
        "logs_criticos": ("system_logs", "severity=eq.critical"),
        "logs_erro": ("system_logs", "severity=eq.error"),
    }
    resultados = {key: 0 for key in metric_specs}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_get_count, table, query, 4): key
            for key, (table, query) in metric_specs.items()
        }
        for future in as_completed(futures):
            resultados[futures[future]] = future.result()
    return resultados

def get_user_by_id(user_id: str):
    url, headers = get_supabase_headers()
    r = requests.get(f"{url}/rest/v1/users?user_id=eq.{user_id}&select=*", headers=headers, timeout=6)
    data = r.json()
    return data[0] if data else None

def get_user_by_email(email: str):
    """Busca usuario pelo email. Retorna dict ou None."""
    url, headers = get_supabase_headers()
    r = requests.get(f"{url}/rest/v1/users?email=eq.{email}&select=*&limit=1", headers=headers, timeout=6)
    data = r.json()
    return data[0] if (data and isinstance(data, list) and len(data) > 0) else None

def mensagem_amigavel_erro_usuario(erro: str) -> str:
    """Traduz erros tecnicos do banco em mensagens seguras para o usuario."""
    texto = str(erro or "")
    texto_lower = texto.lower()
    if "users_whatsapp_key" in texto_lower or ("duplicate key" in texto_lower and "whatsapp" in texto_lower):
        return "Este numero de WhatsApp ja esta cadastrado no sistema. Altere para outro numero ou entre na sua conta."
    if "users_email_key" in texto_lower or ("duplicate key" in texto_lower and "email" in texto_lower):
        return "Este e-mail ja esta cadastrado. Entre na sua conta ou use outro e-mail."
    return texto or "Erro ao salvar usuario."

def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    avatar_url: str = None,
    whatsapp: str = None,
    whatsapp_opt_in: bool = False,
    email_opt_in: bool = False,
    terms_accepted: bool = False,
    privacy_accepted: bool = False,
    ai_notice_accepted: bool = False,
) -> dict:
    """Cria novo usuario com senha hasheada. Retorna {'usuario': ...} ou {'erro': ...}."""
    import uuid

    if get_user_by_email(email):
        return {"erro": "Este e-mail ja esta cadastrado."}

    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"

    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    payload = {
        "user_id":  str(uuid.uuid4()),
        "nome":     nome,
        "email":    email,
        "avatar_url": (avatar_url or "").strip() or None,
        "whatsapp": whatsapp,
        "whatsapp_opt_in": bool(whatsapp and whatsapp_opt_in),
        "email_opt_in": bool(email_opt_in),
        "terms_accepted_at": datetime.now(timezone.utc).isoformat() if terms_accepted else None,
        "privacy_accepted_at": datetime.now(timezone.utc).isoformat() if privacy_accepted else None,
        "ai_notice_accepted_at": datetime.now(timezone.utc).isoformat() if ai_notice_accepted else None,
        "senha_hash": senha_hash,
        "primeira_tiragem_gratis": True,
        "assinante": False,
        "origem":   "frontend_cadastro"
    }

    r = requests.post(f"{url}/rest/v1/users", headers=post_headers, json=payload)
    data = r.json()

    if isinstance(data, list) and len(data) > 0:
        u = data[0]
        u.pop("senha_hash", None)
        return {"usuario": u}
    if isinstance(data, dict) and data.get("code") in {"PGRST204", "42703"}:
        for key in ("avatar_url", "whatsapp_opt_in", "email_opt_in", "terms_accepted_at", "privacy_accepted_at", "ai_notice_accepted_at"):
            payload.pop(key, None)
        r = requests.post(f"{url}/rest/v1/users", headers=post_headers, json=payload)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            u = data[0]
            u.pop("senha_hash", None)
            return {"usuario": u}

    if isinstance(data, dict) and "code" in data:
        return {"erro": mensagem_amigavel_erro_usuario(data.get("message", "Erro ao criar usuario."))}
    return {"erro": "Erro desconhecido ao criar usuario."}

def verificar_login(email: str, senha: str) -> dict:
    """Verifica email + senha. Retorna {'usuario': ...} ou {'erro': ...}."""
    usuario = get_user_by_email(email)
    if not usuario:
        return {"erro": "E-mail nao encontrado."}

    senha_hash = usuario.get("senha_hash", "")
    if not senha_hash:
        return {"erro": "Conta sem senha. Entre em contato com o suporte."}

    try:
        if bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8")):
            try:
                from datetime import datetime, timezone
                url, headers = get_supabase_headers()
                requests.patch(
                    f"{url}/rest/v1/users?user_id=eq.{usuario.get('user_id')}",
                    headers=headers,
                    json={"last_login_at": datetime.now(timezone.utc).isoformat()},
                    timeout=5,
                )
            except Exception:
                pass
            usuario.pop("senha_hash", None)
            return {"usuario": usuario}
        return {"erro": "Senha incorreta."}
    except Exception:
        return {"erro": "Erro ao verificar senha."}

def criar_token_recuperacao(email: str) -> dict:
    usuario = get_user_by_email(email)
    if not usuario:
        return {"ok": True, "mensagem": "Se o e-mail existir, enviaremos as instrucoes."}

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("PASSWORD_RESET_MINUTES", "30")))).isoformat()
    registro = criar_registro("password_reset_tokens", {
        "user_id": usuario["user_id"],
        "token_hash": token_hash,
        "expires_at": expires_at,
    })
    if "erro" in registro:
        return registro
    return {
        "ok": True,
        "token": token,
        "expires_at": expires_at,
        "user_id": usuario["user_id"],
        "email": usuario.get("email"),
        "nome": usuario.get("nome"),
    }

def redefinir_senha_por_token(token: str, nova_senha: str) -> dict:
    if len(nova_senha or "") < 8:
        return {"erro": "A nova senha deve ter pelo menos 8 caracteres."}

    token_hash = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    rows = listar_registros(
        "password_reset_tokens",
        select="*",
        filtros=f"token_hash=eq.{token_hash}",
        limit=1,
    )
    if not rows:
        return {"erro": "Token invalido ou expirado."}

    reset = rows[0]
    if reset.get("used_at"):
        return {"erro": "Token ja utilizado."}

    try:
        expires_at = datetime.fromisoformat(str(reset["expires_at"]).replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            return {"erro": "Token expirado."}
    except Exception:
        return {"erro": "Token expirado."}

    novo_hash = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    atualizado = atualizar_registro("users", "user_id", reset["user_id"], {"senha_hash": novo_hash})
    if "erro" in atualizado:
        return atualizado

    atualizar_registro(
        "password_reset_tokens",
        "reset_id",
        reset["reset_id"],
        {"used_at": datetime.now(timezone.utc).isoformat()},
    )
    registrar_log(
        "PASSWORD_RESET",
        "Senha redefinida por token.",
        user_id=reset["user_id"],
        severity="info",
    )
    return {"ok": True, "user_id": reset["user_id"]}

def atualizar_usuario(user_id: str, nome: str = None, avatar_url: str = None, whatsapp: str = None, whatsapp_opt_in: bool = None, email_opt_in: bool = None) -> dict:
    """Atualiza dados editaveis do perfil. E-mail fica protegido por enquanto."""
    payload = {}
    if nome is not None:
        payload["nome"] = nome.strip()
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url.strip() or None
    if whatsapp is not None:
        payload["whatsapp"] = whatsapp.strip() or None
    if whatsapp_opt_in is not None:
        payload["whatsapp_opt_in"] = bool(whatsapp_opt_in)
        payload["whatsapp_opt_in_at"] = datetime.now(timezone.utc).isoformat() if whatsapp_opt_in else None
        payload["whatsapp_opt_out_at"] = None if whatsapp_opt_in else datetime.now(timezone.utc).isoformat()
    if email_opt_in is not None:
        payload["email_opt_in"] = bool(email_opt_in)
        payload["email_opt_in_at"] = datetime.now(timezone.utc).isoformat() if email_opt_in else None
        payload["email_opt_out_at"] = None if email_opt_in else datetime.now(timezone.utc).isoformat()

    if not payload:
        return {"erro": "Nenhum dado enviado para atualizar."}

    url, headers = get_supabase_headers()
    patch_headers = dict(headers)
    patch_headers["Prefer"] = "return=representation"

    r = requests.patch(
        f"{url}/rest/v1/users?user_id=eq.{user_id}",
        headers=patch_headers,
        json=payload
    )
    data = r.json()

    if isinstance(data, dict) and data.get("code") in {"PGRST204", "42703"}:
        for key in ("avatar_url", "whatsapp_opt_in", "whatsapp_opt_in_at", "whatsapp_opt_out_at", "email_opt_in", "email_opt_in_at", "email_opt_out_at"):
            payload.pop(key, None)
        r = requests.patch(
            f"{url}/rest/v1/users?user_id=eq.{user_id}",
            headers=patch_headers,
            json=payload
        )
        data = r.json()

    if isinstance(data, list) and data:
        usuario = data[0]
        usuario.pop("senha_hash", None)
        return {"usuario": usuario}
    if isinstance(data, dict) and "message" in data:
        return {"erro": mensagem_amigavel_erro_usuario(data.get("message"))}
    return {"erro": "Nao foi possivel atualizar o perfil."}

def exportar_dados_usuario(user_id: str) -> dict:
    usuario = get_user_by_id(user_id) or {}
    usuario.pop("senha_hash", None)
    return {
        "usuario": usuario,
        "perguntas": listar_registros("questions", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "cartas_do_dia": listar_registros("daily_cards", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "pagamentos": listar_registros("payments", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "assinaturas": listar_registros("subscriptions", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "compras_rituais": listar_registros("ritual_purchases", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "mensagens": listar_registros("message_events", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "notificacoes": listar_registros("notification_logs", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
        "logs": listar_registros("system_logs", select="*", filtros=f"user_id=eq.{user_id}", limit=1000),
    }

def anonimizar_usuario(user_id: str, reason: str = None) -> dict:
    usuario = get_user_by_id(user_id)
    if not usuario:
        return {"erro": "Usuario nao encontrado."}
    anon_email = f"deleted-{user_id}@madamedoluar.local"
    payload = {
        "nome": "Conta excluida",
        "email": anon_email,
        "whatsapp": None,
        "whatsapp_opt_in": False,
        "email_opt_in": False,
        "status": "inativo",
        "senha_hash": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    atualizado = atualizar_registro("users", "user_id", user_id, payload)
    if "erro" in atualizado and any(k in str(atualizado["erro"]) for k in ("email_opt_in", "updated_at")):
        payload.pop("email_opt_in", None)
        payload.pop("updated_at", None)
        atualizado = atualizar_registro("users", "user_id", user_id, payload)
    if "erro" in atualizado:
        return atualizado
    try:
        atualizar_registro("message_events", "user_id", user_id, {"status": "cancelled", "error_message": "Conta excluida por solicitacao LGPD."})
    except Exception:
        pass
    registrar_auditoria(
        "ACCOUNT_DELETED",
        entity_type="users",
        entity_id=user_id,
        user_id=user_id,
        before_data={"email": usuario.get("email"), "whatsapp": bool(usuario.get("whatsapp"))},
        after_data={"email": anon_email, "status": "inativo"},
        metadata={"reason": reason},
        severity="warning",
    )
    atualizado.pop("senha_hash", None)
    return {"usuario": atualizado}

def alterar_senha(user_id: str, senha_atual: str, nova_senha: str) -> dict:
    """Troca a senha somente depois de validar a senha atual."""
    usuario = get_user_by_id(user_id)
    if not usuario:
        return {"erro": "Usuario nao encontrado."}

    senha_hash = usuario.get("senha_hash", "")
    if not senha_hash:
        return {"erro": "Conta sem senha cadastrada."}

    try:
        senha_ok = bcrypt.checkpw(senha_atual.encode("utf-8"), senha_hash.encode("utf-8"))
    except Exception:
        return {"erro": "Erro ao verificar senha atual."}

    if not senha_ok:
        return {"erro": "Senha atual incorreta."}

    if len(nova_senha or "") < 8:
        return {"erro": "A nova senha deve ter pelo menos 8 caracteres."}

    novo_hash = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    url, headers = get_supabase_headers()
    requests.patch(
        f"{url}/rest/v1/users?user_id=eq.{user_id}",
        headers=headers,
        json={"senha_hash": novo_hash}
    )
    return {"status": "ok"}

def has_daily_card_today(user_id: str) -> bool:
    from datetime import date
    url, headers = get_supabase_headers()
    hoje = str(date.today())
    r = requests.get(
        f"{url}/rest/v1/daily_cards?user_id=eq.{user_id}&criado_em=eq.{hoje}&select=daily_id",
        headers=headers
    )
    data = r.json()
    return bool(data and len(data) > 0)

def insert_daily_card(user_id: str, carta: str, invertida: bool, mensagem: str):
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    payload = {"user_id": user_id, "carta": carta, "inverted": invertida, "mensagem": mensagem}
    r = requests.post(f"{url}/rest/v1/daily_cards", headers=post_headers, json=payload)
    return r.json()

def insert_question(user_id: str, pergunta: str, tema: str = None) -> str:
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    payload = {"user_id": user_id, "pergunta": pergunta, "tema": tema}
    r = requests.post(f"{url}/rest/v1/questions", headers=post_headers, json=payload)
    data = r.json()
    if data and len(data) > 0:
        return data[0]["question_id"]
    return None

def insert_reading(
    question_id: str,
    cartas: dict,
    interpretacao: str,
    prompt_id: str = None,
    model: str = None,
    tokens_used: int = 0,
    estimated_cost: float = 0,
    status: str = "concluida",
    error_message: str = None,
):
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    payload = {
        "question_id":      question_id,
        "carta_passado":    cartas["passado"]["nome"],
        "inverted_passado": cartas["passado"]["invertida"],
        "carta_presente":   cartas["presente"]["nome"],
        "inverted_presente": cartas["presente"]["invertida"],
        "carta_futuro":     cartas["futuro"]["nome"],
        "inverted_futuro":  cartas["futuro"]["invertida"],
        "interpretacao":    interpretacao,
        "prompt_id":        prompt_id,
        "model":            model,
        "tokens_used":      tokens_used,
        "estimated_cost":   estimated_cost,
        "status":           status,
        "error_message":    error_message,
    }
    r = requests.post(f"{url}/rest/v1/readings", headers=post_headers, json=payload)
    data = _safe_json(r)
    if isinstance(data, list) and data:
        return data[0]
    return data

def registrar_pagamento(user_id: str, status: str, valor: float, tipo: str, gateway_ref: str):
    """Registra uma transacao de pagamento na tabela payments."""
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    payload = {
        "user_id": user_id,
        "status": status,
        "valor": valor,
        "tipo": tipo,
        "gateway_ref": gateway_ref
    }
    requests.post(f"{url}/rest/v1/payments", headers=post_headers, json=payload)

def atualizar_status_assinatura(user_id: str, status: str, plano: str, gateway_id: str):
    """Atualiza o perfil do usuario para assinante e insere registro na tabela subscriptions."""
    url, headers = get_supabase_headers()
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=representation"
    
    is_assinante = (status == "ativo")
    
    # Atualiza na tabela users
    requests.patch(f"{url}/rest/v1/users?user_id=eq.{user_id}", headers=headers, json={"assinante": is_assinante})
    
    if status == "ativo":
        from datetime import datetime, timezone, timedelta
        hoje = datetime.now(timezone.utc).date()
        dias = 365 if "anual" in plano else 30
        renovacao = hoje + timedelta(days=dias)
        payload = {
            "user_id": user_id,
            "status": status,
            "plano": plano,
            "gateway_id": gateway_id,
            "inicio": hoje.isoformat(),
            "renovacao": renovacao.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        existentes = listar_registros(
            "subscriptions",
            select="subscription_id",
            filtros=f"user_id=eq.{user_id}&status=eq.ativo",
            limit=1,
        )
        if existentes:
            atualizar_registro("subscriptions", "subscription_id", existentes[0]["subscription_id"], payload)
            return

        # Insere nova assinatura
        requests.post(f"{url}/rest/v1/subscriptions", headers=post_headers, json=payload)
    else:
        # Atualiza a assinatura existente para cancelada
        requests.patch(
            f"{url}/rest/v1/subscriptions?user_id=eq.{user_id}&status=eq.ativo",
            headers=headers,
            json={"status": status}
        )

def ajustar_creditos(
    user_id: str,
    amount: int,
    tipo: str,
    reason: str,
    admin_id: str = None,
    related_payment_id: str = None,
    related_reading_id: str = None,
    expires_at: str = None,
):
    """Adiciona, remove, consome ou estorna creditos e registra transacao."""
    if tipo not in ("add", "remove", "consume", "refund"):
        return {"erro": "Tipo de transacao de credito invalido."}
    if amount <= 0:
        return {"erro": "Quantidade de creditos deve ser maior que zero."}
    rpc_result = _rpc("admin_adjust_user_credits", {
        "p_user_id": user_id,
        "p_amount": amount,
        "p_type": tipo,
        "p_reason": reason,
        "p_admin_id": admin_id,
        "p_related_payment_id": related_payment_id,
        "p_related_reading_id": related_reading_id,
        "p_expires_at": expires_at,
    })
    if "erro" in rpc_result:
        return rpc_result

    usuario_atualizado = get_user_by_id(user_id)
    if usuario_atualizado:
        usuario_atualizado.pop("senha_hash", None)

    registrar_log(
        event_type="CREDITS_ADDED" if tipo in ("add", "refund") else "CREDITS_REMOVED",
        description=f"Creditos alterados: {tipo} {amount}. Motivo: {reason}",
        user_id=user_id,
        admin_id=admin_id,
        metadata={
            "type": tipo,
            "amount": amount,
            "reason": reason,
            "related_payment_id": related_payment_id,
            "related_reading_id": related_reading_id,
            "expires_at": expires_at,
            "rpc": rpc_result,
        },
        severity="info",
    )
    return {"usuario": usuario_atualizado, **rpc_result}
