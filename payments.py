"""
Pasarelas de pago (PayPal y Mercado Pago) — lado servidor.
Las llaves SECRETAS viven solo en el .env del backend (o en Environment de Render).
El servidor calcula el total desde la BD y VERIFICA con la pasarela el pago real.
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


# ---- A) Tarjeta dentro de la página (Bricks + API Orders) ----

def mp_cobrar_tarjeta(pedido_id: int, total: float, datos: dict) -> dict:
    """Cobra el token generado por CardPayment Brick usando POST /v1/payments.

    Este endpoint es el compatible con el formulario CardPayment de @mercadopago/sdk-react.
    El importe y la referencia siempre se toman del pedido del servidor.
    """
    if not isinstance(datos, dict) or not datos.get("token") or not datos.get("payment_method_id"):
        raise Exception(
            "Mercado Pago no recibió el token o el método de pago. "
            "Verifica los datos de la tarjeta e inténtalo de nuevo."
        )

    payer_recibido = datos.get("payer") or {}
    email = os.getenv("MP_PAYER_EMAIL_PRUEBA") or payer_recibido.get("email")
    if not email:
        raise Exception("Mercado Pago no recibió el correo del comprador.")

    monto = round(float(total), 2)
    body = {
        "transaction_amount": monto,
        "token": datos["token"],
        "description": f"FACC Music - Pedido #{pedido_id}",
        "installments": int(datos.get("installments") or 1),
        "payment_method_id": datos["payment_method_id"],
        "external_reference": str(pedido_id),
        "payer": {"email": email},
    }

    # Algunos métodos de pago devuelven issuer_id; solo se envía si existe.
    if datos.get("issuer_id") not in (None, ""):
        body["issuer_id"] = str(datos["issuer_id"])

    # Mercado Pago puede exigir identificación según el método/país.
    identificacion = payer_recibido.get("identification") or {}
    if identificacion.get("type") and identificacion.get("number"):
        body["payer"]["identification"] = {
            "type": identificacion["type"],
            "number": identificacion["number"],
        }

    headers = {
        **_mp_headers(),
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }
    try:
        r = requests.post(
            f"{MP_API}/v1/payments",
            headers=headers,
            json=body,
            timeout=30,
        )
        try:
            d = r.json()
        except ValueError:
            d = {}
    except requests.RequestException as exc:
        raise Exception("No fue posible conectar con Mercado Pago. Intenta nuevamente.") from exc

    if r.status_code not in (200, 201):
        cause = d.get("cause") or []
        detalle = cause[0].get("description") if cause and isinstance(cause[0], dict) else None
        mensaje = detalle or d.get("message") or r.text[:250]
        raise Exception(f"Mercado Pago rechazó la solicitud: {mensaje}")

    return {
        "id": str(d.get("id", "")),
        "status": d.get("status", "unknown"),
        "status_detail": d.get("status_detail"),
        "reference_id": d.get("external_reference"),
        "monto": float(d.get("transaction_amount") or 0),
        "moneda": d.get("currency_id"),
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