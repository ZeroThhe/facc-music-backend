"""
Prueba rápida de Mercado Pago SIN abrir la tienda.

Hace lo mismo que el Card Payment Brick + tu backend:
  1) tokeniza una tarjeta de PRUEBA con la Public Key
  2) cobra $10 MXN con el Access Token

Uso (desde la carpeta back, con el .env ya lleno):
    python probar_mp.py

Resultado esperado con credenciales de prueba:  status = approved
"""
import os
import uuid

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "")
ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
API = "https://api.mercadopago.com"

if not PUBLIC_KEY or not ACCESS_TOKEN:
    raise SystemExit("Faltan MP_PUBLIC_KEY y/o MP_ACCESS_TOKEN en back/.env")

print(f"Public Key : {PUBLIC_KEY[:12]}...  Access Token: {ACCESS_TOKEN[:12]}...")
me = requests.get(f"{API}/users/me", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, timeout=20).json()
print("Cuenta del token:", me.get("id"), me.get("nickname"))

# 1) Token de tarjeta (Mastercard de prueba de México, titular APRO = pago aprobado)
r = requests.post(
    f"{API}/v1/card_tokens",
    params={"public_key": PUBLIC_KEY},
    json={
        "card_number": "5474925432670366",
        "security_code": "123",
        "expiration_month": 11,
        "expiration_year": 2030,
        "cardholder": {"name": "APRO"},
    },
    timeout=20,
)
token = r.json().get("id") if r.headers.get("content-type", "").startswith("application/json") else None
print(f"\n1) Token de tarjeta -> HTTP {r.status_code}", "OK" if token else f"FALLÓ: {r.text[:300]}")
if not token:
    raise SystemExit("\nLa Public Key no sirve (revisa que sea la de PRUEBA y de la misma aplicación).")

# 2) Cobro con la API de Orders
r = requests.post(
    f"{API}/v1/orders",
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "X-Idempotency-Key": str(uuid.uuid4())},
    json={
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": "10.00",
        "external_reference": "prueba-facc-1",
        "payer": {"email": "test_user_8034134390079183226@testuser.com"},
        "transactions": {
            "payments": [{
                "amount": "10.00",
                "payment_method": {
                    "id": "master",
                    "type": "credit_card",
                    "token": token,
                    "installments": 1,
                },
            }]
        },
    },
    timeout=20,
)
print(f"\n2) Orders -> HTTP {r.status_code}")
print(r.text[:800])
