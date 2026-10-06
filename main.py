"""
Servidor Principal FastAPI con Strawberry GraphQL para FACC Music.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from strawberry.fastapi import GraphQLRouter
from database import init_db, get_db_connection
from schema import schema
from auth import get_context, migrar_passwords, verify_password, crear_token

# 1. Inicializar bases de datos (PostgreSQL + MongoDB)
init_db()
migrar_passwords()  # Hashea con bcrypt cualquier contraseña en texto plano (idempotente)

# 2. Instanciar FastAPI
app = FastAPI(
    title="FACC Music — Backend GraphQL API",
    description="Servidor GraphQL para el E-Commerce de discos, vinilos y CDs (PWII Práctica P2-6)",
    version="1.0.0"
)

# 3. Habilitar CORS para permitir peticiones desde React / Vite (http://localhost:5173)
# Nota: allow_origins=["*"] junto con allow_credentials=True no es una combinación
# válida (el navegador la rechaza), por eso se fija el origen exacto del frontend.
app.add_middleware(
    CORSMiddleware,
    # http://localhost:4321 = Astro dev (npm run dev)
    # http://localhost:4322 = Astro preview (npm run preview), por si 4321 está ocupado
    # http://localhost:5173 = se deja por compatibilidad con el front antiguo en Vite puro
    allow_origins=["http://localhost:4321", "http://localhost:4322", "http://localhost:5173", "https://migracionastro.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Integrar el Router de Strawberry GraphQL en /graphql
# context_getter=get_context expone info.context["user"] a cada resolver protegido
graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")


# 5. Endpoint OAuth2 estándar (flujo Password Bearer)
# El cliente manda credenciales como formulario (no JSON): username + password.
# 'username' es el nombre que exige el spec OAuth2, aunque aquí guardamos el correo ahí.
@app.post("/token", tags=["Auth"])
def login_oauth2(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    r = conn.execute("SELECT * FROM usuarios WHERE email = %s", (form_data.username,)).fetchone()
    conn.close()

    if not r or not verify_password(form_data.password, r["password"]):
        raise HTTPException(
            status_code=401,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": crear_token(r["id"], r["rol"]), "token_type": "bearer"}


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "proyecto": "FACC Music",
        "alumna": "Fátima Martín del Campo Castellanos (22300884)",
        "materia": "Programación Web 2 (PWII) - Práctica P2-6",
        "profesor": "Kegovc",
        "graphql_endpoint": "http://localhost:8000/graphql",
        "token_endpoint": "http://localhost:8000/token",
        "instrucciones": "Abre http://localhost:8000/graphql en tu navegador para interactuar con la consola GraphiQL Playground. Para autenticarte, usa POST http://localhost:8000/token con 'username' (correo) y 'password' como formulario."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)