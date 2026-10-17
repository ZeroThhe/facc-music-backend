"""Autenticacion: hash de contrasenas, JWT y permisos GraphQL."""
import os
import datetime
import bcrypt
import jwt
from fastapi import Request, WebSocket
from fastapi.security import OAuth2PasswordBearer
from strawberry.permission import BasePermission
from database import get_db_connection

SECRET_KEY = os.getenv("JWT_SECRET", "cambia-esto-en-produccion-facc-music")
ALGORITHM = "HS256"
EXPIRA_HORAS = 8

# Declara el esquema OAuth2 (flujo Password). tokenUrl debe coincidir con el
# endpoint @app.post("/token") de main.py. Esto es lo que hace aparecer el
# botón "Authorize" en http://localhost:8000/docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    payload = {
        "sub": str(usuario_id),
        "rol": rol,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=EXPIRA_HORAS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_from_request(request):
    """Lee el token de 'Authorization: Bearer <token>' (HTTP) o de '?token=' (WebSocket)."""
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.query_params.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

    conn = get_db_connection()
    r = conn.execute("SELECT id, nombre, email, rol FROM usuarios WHERE id = %s", (user_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


async def get_context(request: Request = None, ws: WebSocket = None):
    conn = request if request is not None else ws
    return {"request": conn, "user": get_user_from_request(conn)}


def migrar_passwords():
    """Convierte contraseñas en texto plano (las de db.sql) a bcrypt. Es idempotente."""
    conn = get_db_connection()
    for r in conn.execute("SELECT id, password FROM usuarios").fetchall():
        if not r["password"].startswith("$2"):
            conn.execute("UPDATE usuarios SET password = %s WHERE id = %s",
                         (hash_password(r["password"]), r["id"]))
    conn.commit()
    conn.close()


# Permisos reutilizables para Strawberry
class IsAuthenticated(BasePermission):
    message = "Debes iniciar sesión para hacer esto"

    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context["user"] is not None


class IsAdmin(BasePermission):
    message = "Solo un administrador puede hacer esto"

    def has_permission(self, source, info, **kwargs) -> bool:
        user = info.context["user"]
        return user is not None and user["rol"] == "ADMIN"