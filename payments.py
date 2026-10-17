"""
Pasarelas de pago (PayPal y Mercado Pago) — lado servidor.

Las llaves SECRETAS viven solo aquí (archivo .env del backend), nunca en el front.
El servidor es quien crea la orden con el total calculado desde la BD y quien
VERIFICA con la pasarela que el pago realmente se completó antes de marcar
el pedido como PAGADO.
"""
import os
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
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "")      # pública: el front la usa para dibujar el formulario de tarjeta
MP_API = "https://api.mercadopago.com"


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
    """Crea la orden en PayPal y regresa su ID."""
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
    """Captura (cobra) la orden aprobada por el comprador.
    Regresa {status, reference_id, monto, moneda, capture_id}."""
    headers = {"Authorization": f"Bearer {_paypal_token()}", "Content-Type": "application/json"}
    r = requests.post(f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture", headers=headers, timeout=20)
    data = r.json()

    # Si ya se había capturado antes, solo consultamos la orden
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


# ===================== MERCADO PAGO (Checkout Bricks) =====================
# El cliente llena el formulario de tarjeta DENTRO de nuestra página (Card Payment Brick).
# Mercado Pago convierte la tarjeta en un "token" y aquí el servidor hace el cobro.
# No hay redirección a la página de Mercado Pago.

def _mp_headers() -> dict:
    if not MP_ACCESS_TOKEN:
        raise Exception("Falta MP_ACCESS_TOKEN en back/.env")
    return {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}


def mp_cobrar_tarjeta(pedido_id: int, total: float, datos: dict) -> dict:
    """Cobra con tarjeta usando la API de Orders de Mercado Pago.
    El monto sale de la BD (total), nunca del front.
    Regresa el mismo formato de antes: status 'approved' / 'rejected' / 'in_process'."""
    if not isinstance(datos, dict) or not datos.get("token") or not datos.get("payment_method_id"):
        raise Exception("Los datos de la tarjeta llegaron incompletos. Vuelve a llenar el formulario.")

    payer = datos.get("payer") or {}
    # Opcional: para pruebas puedes forzar un correo con MP_PAYER_EMAIL_PRUEBA en .env
    email = os.getenv("MP_PAYER_EMAIL_PRUEBA") or payer.get("email")
    if not email:
        raise Exception("Falta el correo del comprador")

    headers = {
        **_mp_headers(),
        "X-Idempotency-Key": str(uuid.uuid4()),   # una llave única por intento
    }
    monto = f"{round(total, 2):.2f}"              # Orders pide el monto como texto: "10.00"
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
        errores = d.get("errors") or []
        msg = errores[0].get("message") if errores else (d.get("message") or r.text[:200])
        raise Exception(f"Mercado Pago no pudo procesar la tarjeta: {msg}")

    pago = ((d.get("transactions") or {}).get("payments") or [{}])[0]
    estado_mp = pago.get("status") or d.get("status")
    detalle = pago.get("status_detail") or d.get("status_detail")

    # Orders usa otros nombres de estado; los traducimos a los que ya usa tu backend
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