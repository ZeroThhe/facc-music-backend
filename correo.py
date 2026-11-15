"""
API de Gmail — envío de correos al cliente (bienvenida, pago confirmado, cambio de estado).
Usa la Gmail API por HTTPS (no SMTP), por eso funciona en el plan gratis de Render.
Credenciales en back/.env: GMAIL_USER, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN
"""
import base64
import os
import threading
from email.message import EmailMessage

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:4321").rstrip("/")


def _access_token() -> str:
    """Cambia el refresh token (permanente) por un access token (dura 1 hora)."""
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GMAIL_CLIENT_ID,
        "client_secret": GMAIL_CLIENT_SECRET,
        "refresh_token": GMAIL_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=15)
    if r.status_code != 200:
        raise Exception(f"Google rechazó las credenciales de Gmail: {r.text[:200]}")
    return r.json()["access_token"]


def enviar(para: str, asunto: str, html: str):
    """Envía un correo HTML con la Gmail API."""
    if not (GMAIL_USER and GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN):
        print("Gmail: faltan credenciales en back/.env, no se envió el correo", flush=True)
        return

    msg = EmailMessage()
    msg["From"] = f"FACC Music <{GMAIL_USER}>"
    msg["To"] = para
    msg["Subject"] = asunto
    msg.set_content("Abre este correo en un cliente que muestre HTML.")
    msg.add_alternative(html, subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    r = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"raw": raw},
        timeout=20,
    )
    if r.status_code != 200:
        raise Exception(f"Gmail no pudo enviar el correo: {r.text[:200]}")
    print(f"Gmail: correo enviado a {para} ({asunto})", flush=True)


def enviar_en_segundo_plano(para: str, asunto: str, html: str):
    """Manda el correo sin hacer esperar al usuario. Si falla, solo se registra en los logs."""
    def tarea():
        try:
            enviar(para, asunto, html)
        except Exception as e:
            print("Gmail ERROR:", e, flush=True)
    threading.Thread(target=tarea, daemon=True).start()


# ---------------- Plantillas ----------------

def _plantilla(titulo: str, cuerpo: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;background:#180D09;color:#FDE68A;border-radius:16px;overflow:hidden">
      <div style="background:linear-gradient(90deg,#F59E0B,#EC4899);padding:18px 24px">
        <h1 style="margin:0;color:#fff;font-size:22px">FACC Music</h1>
      </div>
      <div style="padding:24px">
        <h2 style="color:#FBBF24;margin-top:0">{titulo}</h2>
        {cuerpo}
        <p style="margin-top:24px"><a href="{FRONT_URL}" style="background:#EC4899;color:#fff;padding:10px 18px;border-radius:999px;text-decoration:none;font-weight:bold">Ir a la tienda</a></p>
      </div>
    </div>"""


def correo_bienvenida(email: str, nombre: str):
    html = _plantilla(f"¡Bienvenido, {nombre}!",
                      "<p>Tu cuenta en FACC Music quedó creada. Ya puedes comprar vinilos y CDs, "
                      "y buscar en Discogs los álbumes que no encuentres.</p>")
    enviar_en_segundo_plano(email, "Bienvenido a FACC Music", html)


def correo_pedido_pagado(email: str, nombre: str, pedido):
    html = _plantilla("¡Recibimos tu pago!",
                      f"<p>Hola {nombre}, tu pedido <b>#{pedido.id}</b> quedó pagado.</p>"
                      f"<p><b>Total:</b> ${pedido.total:.2f} MXN<br>"
                      f"<b>Método:</b> {pedido.metodo_pago}<br>"
                      f"<b>Envío a:</b> {pedido.direccion_envio}</p>"
                      "<p>Te avisaremos por correo cuando cambie el estado de tu envío.</p>")
    enviar_en_segundo_plano(email, f"Pedido #{pedido.id} pagado", html)


def correo_cambio_estado(email: str, nombre: str, pedido):
    html = _plantilla(f"Tu pedido #{pedido.id} ahora está: {pedido.status}",
                      f"<p>Hola {nombre}, hay una actualización de tu pedido.</p>"
                      f"<p><b>Estado:</b> {pedido.status}<br><b>Envío a:</b> {pedido.direccion_envio}</p>"
                      "<p>Puedes ver el mapa de entrega en <b>Mis pedidos</b>.</p>")
    enviar_en_segundo_plano(email, f"Pedido #{pedido.id}: {pedido.status}", html)
