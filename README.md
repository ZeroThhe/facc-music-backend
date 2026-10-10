# FACC Music — Backend GraphQL

Servidor GraphQL para el e-commerce de discos, vinilos y CDs **FACC Music**.
Construido con **Python 3**, **FastAPI**, **Strawberry GraphQL**, **PostgreSQL** y **MongoDB**.

| Base de datos | Qué guarda | Archivo semilla |
|---|---|---|
| PostgreSQL | usuarios, pedidos, detalles_pedido | `db.sql` |
| MongoDB | categorias, productos (catálogo) | `catalogo.json` |

Al arrancar, el servidor crea las tablas y carga el catálogo automáticamente si están vacíos.

**Alumna:** Fátima Martín del Campo Castellanos (Registro: 22300884)  
**Materia:** Programación Web 2 (PWII) · **Profesor:** Kegovc  
**Práctica:** P2-6 (Flujo e-commerce + Backend GraphQL)

---

## 🚀 Requisitos e Instalación

1. **Python 3.9+** instalado.
2. **PostgreSQL** corriendo en `localhost:5432` con una base vacía llamada `facc_music`:
   ```bash
   psql -U postgres -c "CREATE DATABASE facc_music;"
   ```
3. **MongoDB** corriendo en `localhost:27017` (la base `facc_music` se crea sola).
4. Si tu usuario/contraseña de PostgreSQL no es `postgres/postgres`, define la variable:
   ```bash
   # Windows (PowerShell)
   $env:DATABASE_URL="postgresql://USUARIO:CONTRASEÑA@localhost:5432/facc_music"
   ```
5. Instalar las dependencias necesarias:
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

### Mutation: Registrar Pedido (queda PENDIENTE hasta que se paga)
```graphql
mutation {
  registrarPedido(datos: {
    direccionEnvio: "Av. Universidad #120, Guadalajara",
    metodoPago: "PayPal",
    detalles: [{ productoId: 1, cantidad: 1 }]
  }) { id total status }
}
```
El usuario sale del token y los precios los toma el servidor de MongoDB.

## 💳 Pagos (PayPal y Mercado Pago)

1. Copia `.env.example` como `.env` (en esta carpeta `back/`) y llena credenciales de prueba y URLs de las BD.
2. Flujo PayPal: `registrarPedido` → `crearOrdenPaypal(pedidoId)` → el comprador aprueba → `capturarPagoPaypal(pedidoId, orderId)`.
3. Flujo Mercado Pago: `registrarPedido` → `crearPagoMercadoPago(pedidoId)` (regresa URL) → el comprador paga y regresa → `confirmarPagoMercadoPago(pedidoId, paymentId)`.

El servidor consulta a la pasarela, verifica monto, moneda y pedido, y solo entonces marca **PAGADO** (PostgreSQL) y descuenta stock (MongoDB).
