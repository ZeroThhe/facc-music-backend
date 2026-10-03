import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "facc_music.db") 
SQL_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "db.sql")
def get_db_connection():
    """Retorna una conexión activa a la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos si no existe ejecutando db.sql."""
    if not os.path.exists(DB_PATH):
        print("==> Inicializando base de datos desde db.sql...")
        conn = sqlite3.connect(DB_PATH)
        if os.path.exists(SQL_SCRIPT_PATH):
            with open(SQL_SCRIPT_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()
            print("[OK] Base de datos FACC Music inicializada correctamente.")
        else:
            print("[WARN] db.sql no encontrado.")
        conn.close()
