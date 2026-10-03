# FACC Music — Backend GraphQL

Servidor GraphQL para el e-commerce de discos, vinilos y CDs **FACC Music**.
Construido con **Python 3**, **FastAPI**, **Strawberry GraphQL** y **SQLite** (`db.sql`).

**Alumna:** Fátima Martín del Campo Castellanos (Registro: 22300884)  
**Materia:** Programación Web 2 (PWII) · **Profesor:** Kegovc  
**Práctica:** P2-6 (Flujo e-commerce + Backend GraphQL)

---

## 🚀 Requisitos e Instalación

1. **Python 3.9+** instalado.
2. Instalar las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Levantar el Servidor GraphQL

Ejecuta el siguiente comando dentro de la carpeta `back/`:

```bash
python main.py
```

O directamente con Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

El servidor estará escuchando en:
- **Base URL:** `http://localhost:8000`
- **GraphQL Endpoint & Playground:** `http://localhost:8000/graphql`

---

## 🛠️ Operaciones GraphQL Disponibles

### Query: Obtener Categorías con Productos Anidados
```graphql
query {
  categorias {
    id
    nombre
    descripcion
    productos {
      id
      nombre
      artista
      precio
      formato
    }
  }
}
```

### Query: Catálogo Paginado
```graphql
query {
  productos(limit: 6, offset: 0, busqueda: "Beatles") {
    total
    productos {
      id
      nombre
      artista
      precio
      imagen
    }
  }
}
```

### Mutation: Registrar Pedido
```graphql
mutation {
  registrarPedido(input: {
    usuarioId: 1,
    direccionEnvio: "Av. Universidad #120, Guadalajara",
    metodoPago: "Tarjeta de Crédito",
    detalles: [
      { productoId: 1, cantidad: 1, precioUnitario: 899.00 }
    ]
  }) {
    id
    fecha
    total
    status
  }
}
```
