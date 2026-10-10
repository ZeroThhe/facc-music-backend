"""
Pasarelas de pago (PayPal y Mercado Pago) — lado servidor.

Las llaves SECRETAS viven solo aquí (archivo .env del backend), nunca en el front.
El servidor es quien crea la orden con el total calculado desde la BD y quien
VERIFICA con la pasarela que el pago realmente se completó antes de marcar
el pedido como PAGADO.
"""
import os
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
MP_API = "https://api.mercadopago.com"

# URL del front (a donde Mercado Pago regresa al usuario después de pagar)
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


# ===================== MERCADO PAGO =====================

def _mp_headers() -> dict:
    if not MP_ACCESS_TOKEN:
        raise Exception("Falta MP_ACCESS_TOKEN en back/.env")
    return {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}


def mp_crear_preferencia(pedido_id: int, items: list) -> str:
    """Crea la preferencia (el 'carrito' en Mercado Pago) y regresa la URL de pago."""
    body = {
        "items": [
            {"title": i["titulo"], "quantity": i["cantidad"],
             "unit_price": float(i["precio"]), "currency_id": MONEDA}
            for i in items
        ],
        # Así sabemos a qué pedido pertenece el pago cuando el usuario regrese
        "external_reference": str(pedido_id),
        "back_urls": {"success": f"{FRONT_URL}/", "failure": f"{FRONT_URL}/", "pending": f"{FRONT_URL}/"},
    }
    # Mercado Pago no acepta auto_return con localhost; en local el usuario
    # da clic en "Volver al sitio" al terminar de pagar.
    if "localhost" not in FRONT_URL and "127.0.0.1" not in FRONT_URL:
        body["auto_return"] = "approved"

    r = requests.post(f"{MP_API}/checkout/preferences", headers=_mp_headers(), json=body, timeout=20)
    if r.status_code not in (200, 201):
        raise Exception(f"Mercado Pago no pudo crear la preferencia: {r.text[:200]}")
    return r.json()["init_point"]


def mp_buscar_pago_aprobado(pedido_id: int):
    """Busca en Mercado Pago un pago APROBADO de este pedido (por external_reference).
    Así no dependemos de que el cliente regrese a la tienda con el botón "Volver al sitio"."""
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
    """Pregunta a Mercado Pago el estado real del pago (no confiamos en la URL)."""
    r = requests.get(f"{MP_API}/v1/payments/{payment_id}", headers=_mp_headers(), timeout=20)
    if r.status_code != 200:
        raise Exception("No se encontró el pago en Mercado Pago")
    d = r.json()
    return {
        "status": d["status"],  # approved, pending, rejected...
        "reference_id": d.get("external_reference"),
        "monto": float(d["transaction_amount"]),
        "moneda": d.get("currency_id"),
    }
