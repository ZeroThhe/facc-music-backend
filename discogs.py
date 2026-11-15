"""
API de Discogs — buscar álbumes en el catálogo mundial de Discogs.
El token vive solo en el .env del backend (DISCOGS_TOKEN), nunca en el front.
Docs: https://www.discogs.com/developers
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN", "")
DISCOGS_API = "https://api.discogs.com"
# Discogs exige un User-Agent que identifique a la aplicación
USER_AGENT = "FACCMusic/1.0"


def buscar_albumes(texto: str, limite: int = 12) -> list:
    """Busca álbumes (releases) en Discogs por artista o título."""
    if not DISCOGS_TOKEN:
        raise Exception("Falta DISCOGS_TOKEN en back/.env")
    if not texto.strip():
        return []

    r = requests.get(
        f"{DISCOGS_API}/database/search",
        headers={"User-Agent": USER_AGENT, "Authorization": f"Discogs token={DISCOGS_TOKEN}"},
        params={"q": texto.strip(), "type": "release", "per_page": limite, "page": 1},
        timeout=15,
    )
    if r.status_code == 401:
        raise Exception("Discogs rechazó el token (revisa DISCOGS_TOKEN)")
    if r.status_code == 429:
        raise Exception("Demasiadas búsquedas seguidas en Discogs. Espera un minuto.")
    if r.status_code != 200:
        raise Exception("No se pudo consultar Discogs")

    albumes = []
    for d in r.json().get("results", []):
        albumes.append({
            "discogs_id": d.get("id"),
            "titulo": d.get("title", "Sin título"),          # viene como "Artista - Álbum"
            "anio": str(d.get("year") or ""),
            "pais": d.get("country") or "",
            "formato": ", ".join(d.get("format") or []),     # ej. "Vinyl, LP, Album"
            "portada": d.get("cover_image") or d.get("thumb") or "",
        })
    return albumes
