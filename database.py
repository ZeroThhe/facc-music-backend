"""
Conexiones a las dos bases de datos de FACC Music:
  - PostgreSQL -> usuarios, pedidos y detalles_pedido (datos transaccionales / relacionales)
  - MongoDB    -> categorias y productos (catálogo en documentos)
"""
import os
import json
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

BASE_DIR = os.path.dirname(__file__)

# Se pueden cambiar con variables de entorno si tu usuario/contraseña son otros
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/facc_music")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "facc_music")

SQL_SCRIPT_PATH = os.path.join(BASE_DIR, "db.sql")
CATALOGO_PATH = os.path.join(BASE_DIR, "catalogo.json")

_mongo_client = MongoClient(MONGO_URL)


def get_db_connection():
    """Conexión a PostgreSQL. Las filas regresan como diccionarios (r["campo"])."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_mongo():
    """Base de datos de MongoDB (colecciones: categorias, productos)."""
    return _mongo_client[MONGO_DB]


def init_db():
    """Crea las tablas en PostgreSQL y carga el catálogo en MongoDB si están vacíos."""
    # --- PostgreSQL ---
    conn = get_db_connection()
    existe = conn.execute("SELECT to_regclass('public.usuarios') AS t").fetchone()["t"]
    if not existe:
        print("==> Creando tablas de PostgreSQL desde db.sql...")
        with open(SQL_SCRIPT_PATH, "r", encoding="utf-8") as f:
            conn.execute(f.read())
        conn.commit()
        print("[OK] PostgreSQL listo.")
    # Migración: columna para el ID del cobro de PayPal / Mercado Pago
    conn.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS referencia_pago VARCHAR(100)")
    conn.commit()
    conn.close()

    # --- MongoDB ---
    db = get_mongo()
    if db.productos.count_documents({}) == 0:
        print("==> Cargando catálogo en MongoDB desde catalogo.json...")
        with open(CATALOGO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        db.categorias.delete_many({})
        db.categorias.insert_many(data["categorias"])
        db.productos.insert_many(data["productos"])
        db.categorias.create_index("id", unique=True)
        db.productos.create_index("id", unique=True)
        print("[OK] MongoDB listo.")
