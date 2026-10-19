"""
Pasarelas de pago (PayPal y Mercado Pago) — lado servidor.
Las llaves SECRETAS viven solo en el .env del backend (o en Environment de Render).
El servidor calcula el total desde la BD y VERIFICA con la pasarela el pago real.
"""
import os
import time
import uuid
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MONEDA = "MXN"

# ---- PayPal (Sandbox) ----
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
PAYPAL_API = "https://api-m.sandbox.paypal.com"

# ---- Mercado Pago ----
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "")   # solo la usa el formulario de tarjeta (Bricks)
MP_API = "https://api.mercadopago.com"

# A donde Mercado Pago regresa al usuario (Checkout Pro)
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:4321").rstrip("/")


# ===================== PAYPAL =====================

def _paypal_token() -> str:
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise Exception("Faltan PAYPAL_CLIENT_ID / PAYPAL_SECRET en back/.env")
    r = requests.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    if r.status_code != 200:
        raise Exception("PayPal rechazó las credenciales (revisa Client ID y Secret)")
    return r.json()["access_token"]


def paypal_crear_orden(pedido_id: int, total: float) -> str:
    r = requests.post(
        f"{PAYPAL_API}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {_paypal_token()}"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": str(pedido_id),
                "description": f"FACC Music - Pedido #{pedido_id}",
                "amount": {"currency_code": MONEDA, "value": f"{total:.2f}"},
            }],
        },
        timeout=20,
    )
    if r.status_code not in (200, 201):
        raise Exception(f"PayPal no pudo crear la orden: {r.text[:200]}")
    return r.json()["id"]


def paypal_capturar(order_id: str) -> dict:
    headers = {"Authorization": f"Bearer {_paypal_token()}", "Content-Type": "application/json"}
    r = requests.post(f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture", headers=headers, timeout=20)
    data = r.json()

    if r.status_code == 422 and "ORDER_ALREADY_CAPTURED" in r.text:
        data = requests.get(f"{PAYPAL_API}/v2/checkout/orders/{order_id}", headers=headers, timeout=20).json()
    elif r.status_code not in (200, 201):
        raise Exception("PayPal no pudo cobrar el pago (método rechazado o orden inválida)")

    unidad = data["purchase_units"][0]
    captura = unidad["payments"]["captures"][0]
    return {
        "status": captura["status"],
        "reference_id": unidad.get("reference_id"),
        "monto": float(captura["amount"]["value"]),
        "moneda": captura["amount"]["currency_code"],
        "capture_id": captura["id"],
    }


# ===================== MERCADO PAGO =====================

def _mp_headers() -> dict:
    if not MP_ACCESS_TOKEN:
        raise Exception("Falta MP_ACCESS_TOKEN en back/.env")
    return {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}


# ---- Mensajes de rechazo ----
# Códigos (status_detail) que devuelve la API de Orders, según la documentación
# de Mercado Pago, traducidos a los textos de la tabla de titulares de prueba.
# Nota: SECU, EXPI, FORM y CARD pueden llegar todos como "bad_filled_card_data".
MENSAJES_RECHAZO_MP = {
    # OTHE
    "cc_rejected_other_reason": "Rechazado por error general.",
    "rejected_by_issuer": "Rechazado por error general (el banco emisor rechazó el pago).",
    "processing_error": "Rechazado por error general (error de procesamiento).",
    # CONT (pendiente)
    "in_process": "Pendiente de pago: el pago aún se está procesando.",
    "pending_review_manual": "Pendiente de pago: el pago está en revisión manual.",
    "pending_contingency": "Pendiente de pago: el pago aún no se acredita.",
    "in_review": "Pendiente de pago: el pago está en revisión.",
    "pending_challenge": "Pendiente de pago: falta completar la autenticación 3DS.",
    "waiting_payment": "Pendiente de pago: se espera el pago.",
    # CALL
    "required_call_for_authorize": "Rechazado con validación para autorizar: llama a tu banco.",
    "cc_rejected_call_for_authorize": "Rechazado con validación para autorizar: llama a tu banco.",
    # FUND
    "insufficient_amount": "Rechazado por importe insuficiente.",
    "card_insufficient_amount": "Rechazado por importe insuficiente.",
    "cc_rejected_insufficient_amount": "Rechazado por importe insuficiente.",
    # SECU / EXPI / FORM / CARD
    "bad_filled_card_data": "Rechazado por datos de tarjeta incorrectos (código de seguridad, fecha de vencimiento, número de tarjeta o error de formulario).",
    "cc_rejected_bad_filled_security_code": "Rechazado por código de seguridad inválido.",
    "cc_rejected_bad_filled_date": "Rechazado por un problema con la fecha de vencimiento.",
    "cc_rejected_bad_filled_other": "Rechazado por un error en el formulario.",
    "cc_rejected_bad_filled_card_number": "Rechazado: falta o es inválido el número de tarjeta.",
    "invalid_card_token": "Rechazado: el token de la tarjeta no es válido. Vuelve a llenar el formulario.",
    # INST
    "invalid_installments": "Rechazado por cuotas inválidas.",
    "cc_rejected_invalid_installments": "Rechazado por cuotas inválidas.",
    # DUPL
    "cc_rejected_duplicated_payment": "Rechazado por pago duplicado.",
    # LOCK
    "card_disabled": "Rechazado por tarjeta deshabilitada.",
    "cc_rejected_card_disabled": "Rechazado por tarjeta deshabilitada.",
    # CTNA
    "cc_rejected_card_type_not_allowed": "Rechazado por tipo de tarjeta no permitido.",
    # ATTE
    "max_attempts_exceeded": "Rechazado debido a intentos excedidos del PIN de la tarjeta.",
    "cc_rejected_max_attempts": "Rechazado debido a intentos excedidos del PIN de la tarjeta.",
    # BLAC / riesgo
    "high_risk": "Rechazado por riesgo alto (por ejemplo, tarjeta en lista negra).",
    "cc_rejected_high_risk": "Rechazado por riesgo alto (por ejemplo, tarjeta en lista negra).",
    "cc_rejected_blacklist": "Rechazado por estar en lista negra.",
    # Otros
    "amount_limit_exceeded": "Rechazado por exceder el límite de importe.",
    "3ds_challenge_expired": "Rechazado: expiró la autenticación 3DS.",
}


def mensaje_rechazo(codigo) -> str:
    c = str(codigo or "").strip().lower()
    if c in MENSAJES_RECHAZO_MP:
        return MENSAJES_RECHAZO_MP[c]
    if c in ("rejected", "failed", ""):
        return "Mercado Pago rechazó el pago, pero no indicó el motivo."
    return f"Mercado Pago rechazó el pago (código: {c})."


def _extraer_pago(d: dict):
    """Devuelve (pago, estado, detalle) de la respuesta de una orden."""
    pago = ((d.get("transactions") or {}).get("payments") or [{}])[0]
    estado = pago.get("status") or d.get("status")
    detalle = pago.get("status_detail") or d.get("status_detail")
    return pago, estado, detalle


def _codigo_error_http(d: dict):
    errores = d.get("errors") or []
    if errores:
        return errores[0].get("code") or errores[0].get("message")
    return d.get("message")


# ---- A) Tarjeta dentro de la página (Bricks + API Orders) ----

def mp_cobrar_tarjeta(pedido_id: int, total: float, datos: dict) -> dict:
    if not isinstance(datos, dict) or not datos.get("token") or not datos.get("payment_method_id"):
        raise Exception("Los datos de la tarjeta llegaron incompletos. Vuelve a llenar el formulario.")

    payer = datos.get("payer") or {}
    email = os.getenv("MP_PAYER_EMAIL_PRUEBA") or payer.get("email")
    if not email:
        raise Exception("Falta el correo del comprador")

    headers = {**_mp_headers(), "X-Idempotency-Key": str(uuid.uuid4())}
    monto = f"{round(total, 2):.2f}"
    body = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": monto,
        "external_reference": str(pedido_id),
        "payer": {"email": email},
        "transactions": {
            "payments": [{
                "amount": monto,
                "payment_method": {
                    "id": datos["payment_method_id"],
                    "type": datos.get("payment_type_id") or "credit_card",
                    "token": datos["token"],
                    "installments": int(datos.get("installments") or 1),
                },
            }]
        },
    }

    r = requests.post(f"{MP_API}/v1/orders", headers=headers, json=body, timeout=30)
    try:
        d = r.json()
    except ValueError:
        d = {}

    if r.status_code not in (200, 201):
        codigo = _codigo_error_http(d)
        print("MP orders ERROR HTTP:", r.status_code, "| respuesta:", str(d)[:500], flush=True)
        raise Exception(mensaje_rechazo(codigo))

    pago, estado_mp, detalle = _extraer_pago(d)

    # La orden puede responder "en proceso" o sin motivo; consultamos el resultado final
    order_id = d.get("id")
    intentos = 0
    while order_id and intentos < 3 and (
        estado_mp in (None, "created", "processing")
        or (estado_mp in ("failed", "canceled") and detalle in (None, "", "failed"))
    ):
        time.sleep(1)
        g = requests.get(f"{MP_API}/v1/orders/{order_id}", headers=_mp_headers(), timeout=20)
        if g.status_code == 200:
            d = g.json()
            pago, estado_mp, detalle = _extraer_pago(d)
        intentos += 1

    # Va a los Logs de Render para ver qué devolvió Mercado Pago en cada intento
    print("MP orders:", "estado =", estado_mp, "| detalle =", detalle, flush=True)

    if estado_mp == "processed":
        status = "approved"
    elif estado_mp in ("failed", "canceled", "expired"):
        status = "rejected"
    else:
        status = "in_process"

    return {
        "id": str(d.get("id") or pago.get("id")),
        "status": status,
        "status_detail": detalle,
        "reference_id": d.get("external_reference"),
        "monto": float(pago.get("paid_amount") or pago.get("amount") or d.get("total_amount") or total),
        "moneda": d.get("currency", MONEDA),
    }


# ---- B) Checkout Pro (redirige a la página de Mercado Pago) ----

def mp_crear_preferencia(pedido_id: int, items: list) -> str:
    body = {
        "items": [
            {"title": i["titulo"], "quantity": i["cantidad"],
             "unit_price": float(i["precio"]), "currency_id": MONEDA}
            for i in items
        ],
        "external_reference": str(pedido_id),
        "back_urls": {"success": f"{FRONT_URL}/", "failure": f"{FRONT_URL}/", "pending": f"{FRONT_URL}/"},
    }
    if "localhost" not in FRONT_URL and "127.0.0.1" not in FRONT_URL:
        body["auto_return"] = "approved"

    r = requests.post(f"{MP_API}/checkout/preferences", headers=_mp_headers(), json=body, timeout=20)
    if r.status_code not in (200, 201):
        raise Exception(f"Mercado Pago no pudo crear la preferencia: {r.text[:200]}")
    return r.json()["init_point"]


def mp_buscar_pago_aprobado(pedido_id: int):
    r = requests.get(
        f"{MP_API}/v1/payments/search",
        headers=_mp_headers(),
        params={"external_reference": str(pedido_id), "sort": "date_created", "criteria": "desc"},
        timeout=20,
    )
    if r.status_code != 200:
        raise Exception("No se pudo consultar Mercado Pago")
    for d in r.json().get("results", []):
        if d.get("status") == "approved":
            return {
                "id": str(d["id"]),
                "status": d["status"],
                "reference_id": d.get("external_reference"),
                "monto": float(d["transaction_amount"]),
                "moneda": d.get("currency_id"),
            }
    return None


def mp_consultar_pago(payment_id: str) -> dict:
    r = requests.get(f"{MP_API}/v1/payments/{payment_id}", headers=_mp_headers(), timeout=20)
    if r.status_code != 200:
        raise Exception("No se encontró el pago en Mercado Pago")
    d = r.json()
    return {
        "status": d["status"],
        "reference_id": d.get("external_reference"),
        "monto": float(d["transaction_amount"]),
        "moneda": d.get("currency_id"),
    }