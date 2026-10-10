"""
Schema SDL GraphQL para FACC Music (PWII - Práctica P2-6)
Materia: Programación Web 2 · Profesor: Kegovc
Alumna: Fátima Martín del Campo Castellanos (22300884)
"""

import enum
from typing import List, Optional
import strawberry
from strawberry.types import Info
import re
from database import get_db_connection, get_mongo
from auth import hash_password, IsAuthenticated, IsAdmin
import payments


# ENUMS Y TIPOS AUXILIARES


@strawberry.enum
class RolEnum(enum.Enum):
    CLIENTE = "CLIENTE"
    ADMIN = "ADMIN"


# HELPERS: convertir documentos de MongoDB en tipos GraphQL

def producto_desde_doc(d) -> "Producto":
    return Producto(
        id=d["id"],
        nombre=d["nombre"],
        artista=d["artista"],
        formato=d["formato"],
        precio=float(d["precio"]),
        imagen=d["imagen"],
        stock=d["stock"],
        destacado=bool(d["destacado"]),
        categoria_id=d["categoria_id"]
    )

def categoria_desde_doc(d) -> "Categoria":
    return Categoria(
        id=d["id"],
        nombre=d["nombre"],
        descripcion=d.get("descripcion"),
        imagen=d.get("imagen")
    )


# TIPOS GRAPHQL (ENTIDADES CON RESOLUTORES ANIDADOS)


@strawberry.type(description="Entidad Categoría con relación a sus Productos")
class Categoria:
    id: int
    nombre: str
    descripcion: Optional[str]
    imagen: Optional[str]

    @strawberry.field(description="Resolutor anidado: Obtener los productos de esta categoría")
    def productos(self) -> List["Producto"]:
        docs = get_mongo().productos.find({"categoria_id": self.id}).sort("id", 1)
        return [producto_desde_doc(d) for d in docs]

@strawberry.type(description="Entidad Producto (Álbum / Vinilo / CD)")
class Producto:
    id: int
    nombre: str
    artista: str
    formato: str
    precio: float
    imagen: str
    stock: int
    destacado: bool
    categoria_id: int

    @strawberry.field(description="Resolutor anidado: Obtener la Categoría del producto")
    def categoria(self) -> Optional[Categoria]:
        d = get_mongo().categorias.find_one({"id": self.categoria_id})
        return categoria_desde_doc(d) if d else None

@strawberry.type(description="Resultado de consulta paginada de productos")
class ProductoPaginado:
    total: int
    productos: List[Producto]

@strawberry.type(description="Entidad Usuario")
class Usuario:
    id: int
    nombre: str
    email: str
    rol: RolEnum

@strawberry.type(description="Renglón / Detalle de Pedido")
class DetallePedido:
    id: int
    pedido_id: int
    producto_id: int
    cantidad: int
    precio_unitario: float

    @strawberry.field(description="Resolutor anidado: Producto comprado en este renglón")
    def producto(self) -> Optional[Producto]:
        d = get_mongo().productos.find_one({"id": self.producto_id})
        return producto_desde_doc(d) if d else None

@strawberry.type(description="Entidad Pedido (Orden de Compra)")
class Pedido:
    id: int
    fecha: str
    total: float
    status: str
    usuario_id: int
    direccion_envio: str
    metodo_pago: str
    referencia_pago: Optional[str] = None

    @strawberry.field(description="Resolutor anidado: Usuario que realizó el pedido")
    def usuario(self) -> Optional[Usuario]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (self.usuario_id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return Usuario(
                id=r["id"],
                nombre=r["nombre"],
                email=r["email"],
                rol=RolEnum(r["rol"])
            )
        return None

    @strawberry.field(description="Resolutor anidado: Lista de renglones/detalles de este pedido")
    def detalles(self) -> List[DetallePedido]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM detalles_pedido WHERE pedido_id = %s ORDER BY id", (self.id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            DetallePedido(
                id=r["id"],
                pedido_id=r["pedido_id"],
                producto_id=r["producto_id"],
                cantidad=r["cantidad"],
                precio_unitario=float(r["precio_unitario"])
            )
            for r in rows
        ]


# INPUTS GRAPHQL (ESCRITURA)


@strawberry.input(description="Datos para crear o actualizar un producto")
class ProductoInput:
    nombre: str
    artista: str
    formato: str
    precio: float
    imagen: str
    stock: int
    destacado: bool
    categoria_id: int

@strawberry.input(description="Renglón del carrito (el precio lo toma el servidor de MongoDB, no el cliente)")
class DetalleInput:
    producto_id: int
    cantidad: int

@strawberry.input(description="Datos para registrar un nuevo pedido (el usuario sale del token, no del input)")
class PedidoInput:
    direccion_envio: str
    metodo_pago: str
    detalles: List[DetalleInput]

@strawberry.input(description="Datos para crear una cuenta nueva")
class RegistroInput:
    nombre: str
    email: str
    password: str


@strawberry.type(description="Datos PÚBLICOS que necesita el front para pintar los botones de pago")
class ConfigPagos:
    paypal_client_id: str
    moneda: str


METODOS_PAGO = ["PayPal", "Mercado Pago"]
STATUS_PEDIDO = ["PENDIENTE", "PAGADO", "ENVIADO", "ENTREGADO", "CANCELADO", "COMPLETADO"]


def fila_a_pedido(r) -> Pedido:
    return Pedido(
        id=r["id"],
        fecha=str(r["fecha"]),
        total=float(r["total"]),
        status=r["status"],
        usuario_id=r["usuario_id"],
        direccion_envio=r["direccion_envio"],
        metodo_pago=r["metodo_pago"],
        referencia_pago=r.get("referencia_pago"),
    )


def pedido_pendiente_del_usuario(conn, pedido_id: int, user: dict, metodo: str):
    """Valida que el pedido exista, sea del usuario y se pague con ese método."""
    r = conn.execute("SELECT * FROM pedidos WHERE id = %s", (pedido_id,)).fetchone()
    if not r or r["usuario_id"] != user["id"]:
        raise Exception("Pedido no encontrado")
    if r["metodo_pago"] != metodo:
        raise Exception(f"Este pedido no se paga con {metodo}")
    return r


def marcar_pagado(conn, pedido_id: int, referencia: str):
    """PENDIENTE -> PAGADO y descuenta stock en MongoDB.
    El WHERE status='PENDIENTE' garantiza que el stock se descuente una sola vez."""
    cambio = conn.execute(
        "UPDATE pedidos SET status = 'PAGADO', referencia_pago = %s WHERE id = %s AND status = 'PENDIENTE' RETURNING id",
        (referencia, pedido_id)
    ).fetchone()
    conn.commit()

    if cambio:
        productos = get_mongo().productos
        for d in conn.execute("SELECT producto_id, cantidad FROM detalles_pedido WHERE pedido_id = %s",
                              (pedido_id,)).fetchall():
            productos.update_one(
                {"id": d["producto_id"]},
                [{"$set": {"stock": {"$max": [0, {"$subtract": ["$stock", d["cantidad"]]}]}}}]
            )
    return fila_a_pedido(conn.execute("SELECT * FROM pedidos WHERE id = %s", (pedido_id,)).fetchone())


def validar_monto(pedido_row, pago: dict):
    if str(pago["reference_id"]) != str(pedido_row["id"]):
        raise Exception("El pago no corresponde a este pedido")
    if pago["moneda"] != payments.MONEDA or abs(pago["monto"] - float(pedido_row["total"])) > 0.01:
        raise Exception("El monto pagado no coincide con el total del pedido")


# OPERACIONES DE LECTURA (QUERIES)


@strawberry.type
class Query:
    @strawberry.field(description="Listar todas las categorías con sus productos anidados")
    def categorias(self) -> List[Categoria]:
        docs = get_mongo().categorias.find().sort("id", 1)
        return [categoria_desde_doc(d) for d in docs]

    @strawberry.field(description="Consultar una categoría por su ID")
    def categoria(self, id: int) -> Optional[Categoria]:
        d = get_mongo().categorias.find_one({"id": id})
        return categoria_desde_doc(d) if d else None

    @strawberry.field(description="Listar el catálogo de productos con paginación y filtros por categoría o búsqueda")
    def productos(
        self,
        limit: Optional[int] = 20,
        offset: Optional[int] = 0,
        categoriaId: Optional[int] = None,
        busqueda: Optional[str] = None
    ) -> ProductoPaginado:
        filtro = {}
        if categoriaId:
            filtro["categoria_id"] = categoriaId
        if busqueda:
            patron = {"$regex": re.escape(busqueda), "$options": "i"}
            filtro["$or"] = [{"nombre": patron}, {"artista": patron}]

        col = get_mongo().productos
        total = col.count_documents(filtro)
        docs = col.find(filtro).sort("id", -1).skip(offset or 0).limit(limit or 20)
        return ProductoPaginado(total=total, productos=[producto_desde_doc(d) for d in docs])

    @strawberry.field(description="Consultar un producto específico por ID")
    def producto(self, id: int) -> Optional[Producto]:
        d = get_mongo().productos.find_one({"id": id})
        return producto_desde_doc(d) if d else None

    @strawberry.field(description="Usuario de la sesión actual (null si no hay token o es inválido)")
    def me(self, info: Info) -> Optional[Usuario]:
        u = info.context["user"]
        if not u:
            return None
        return Usuario(id=u["id"], nombre=u["nombre"], email=u["email"], rol=RolEnum(u["rol"]))

    @strawberry.field(
        description="Historial de pedidos (el ADMIN ve todos, el CLIENTE solo los suyos)",
        permission_classes=[IsAuthenticated]
    )
    def historial_pedidos(self, info: Info) -> List[Pedido]:
        user = info.context["user"]
        conn = get_db_connection()
        cursor = conn.cursor()
        if user["rol"] == "ADMIN":
            cursor.execute("SELECT * FROM pedidos ORDER BY fecha DESC")
        else:
            cursor.execute("SELECT * FROM pedidos WHERE usuario_id = %s ORDER BY fecha DESC", (user["id"],))
        rows = cursor.fetchall()
        conn.close()
        return [fila_a_pedido(r) for r in rows]

    @strawberry.field(description="Configuración pública de pagos (Client ID de PayPal y moneda)")
    def config_pagos(self) -> ConfigPagos:
        return ConfigPagos(paypal_client_id=payments.PAYPAL_CLIENT_ID, moneda=payments.MONEDA)


# OPERACIONES DE ESCRITURA (MUTATIONS)


@strawberry.type
class Mutation:
    @strawberry.mutation(
        description="Crear una cuenta nueva (rol CLIENTE). El login se hace por /token, no aquí."
    )
    def registrar_usuario(self, datos: RegistroInput) -> Usuario:
        email = datos.email.strip().lower()
        if "@" not in email or len(datos.password) < 6:
            raise Exception("Correo inválido o contraseña menor a 6 caracteres")

        conn = get_db_connection()
        try:
            cur = conn.execute(
                "INSERT INTO usuarios (nombre, email, password, rol) VALUES (%s, %s, %s, 'CLIENTE') RETURNING id",
                (datos.nombre.strip(), email, hash_password(datos.password))
            )
            uid = cur.fetchone()["id"]
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise Exception("Ese correo ya está registrado")

        conn.close()
        return Usuario(id=uid, nombre=datos.nombre.strip(), email=email, rol=RolEnum.CLIENTE)

    @strawberry.mutation(description="Registrar un nuevo producto en el catálogo", permission_classes=[IsAdmin])
    def registrar_producto(self, input: ProductoInput) -> Producto:
        col = get_mongo().productos
        ultimo = col.find_one(sort=[("id", -1)])
        new_id = (ultimo["id"] + 1) if ultimo else 1
        col.insert_one({
            "id": new_id,
            "nombre": input.nombre,
            "artista": input.artista,
            "formato": input.formato,
            "precio": input.precio,
            "imagen": input.imagen,
            "stock": input.stock,
            "destacado": input.destacado,
            "categoria_id": input.categoria_id,
        })
        return Producto(
            id=new_id,
            nombre=input.nombre,
            artista=input.artista,
            formato=input.formato,
            precio=input.precio,
            imagen=input.imagen,
            stock=input.stock,
            destacado=input.destacado,
            categoria_id=input.categoria_id
        )

    @strawberry.mutation(description="Actualizar los datos de un producto existente", permission_classes=[IsAdmin])
    def actualizar_producto(self, id: int, input: ProductoInput) -> Optional[Producto]:
        res = get_mongo().productos.update_one({"id": id}, {"$set": {
            "nombre": input.nombre,
            "artista": input.artista,
            "formato": input.formato,
            "precio": input.precio,
            "imagen": input.imagen,
            "stock": input.stock,
            "destacado": input.destacado,
            "categoria_id": input.categoria_id,
        }})
        if res.matched_count == 0:
            return None
        return Producto(
            id=id,
            nombre=input.nombre,
            artista=input.artista,
            formato=input.formato,
            precio=input.precio,
            imagen=input.imagen,
            stock=input.stock,
            destacado=input.destacado,
            categoria_id=input.categoria_id
        )

    @strawberry.mutation(description="Eliminar un producto del catálogo por su ID", permission_classes=[IsAdmin])
    def eliminar_producto(self, id: int) -> bool:
        res = get_mongo().productos.delete_one({"id": id})
        return res.deleted_count > 0

    @strawberry.mutation(
        description="Crear el pedido en estado PENDIENTE (aún sin pagar). Precios y total los calcula el servidor.",
        permission_classes=[IsAuthenticated]
    )
    def registrar_pedido(self, info: Info, datos: PedidoInput) -> Pedido:
        usuario_id = info.context["user"]["id"]
        if datos.metodo_pago not in METODOS_PAGO:
            raise Exception("Método de pago no válido (usa PayPal o Mercado Pago)")
        if not datos.detalles:
            raise Exception("El carrito está vacío")
        if not datos.direccion_envio.strip():
            raise Exception("Falta la dirección de envío")

        # 1) Precios y stock reales desde MongoDB
        renglones = []
        col = get_mongo().productos
        for d in datos.detalles:
            p = col.find_one({"id": d.producto_id})
            if not p:
                raise Exception(f"El producto {d.producto_id} ya no existe")
            if d.cantidad <= 0 or d.cantidad > p["stock"]:
                raise Exception(f"No hay suficiente stock de '{p['nombre']}' (quedan {p['stock']})")
            renglones.append((d.producto_id, d.cantidad, float(p["precio"])))

        total = round(sum(c * precio for _, c, precio in renglones), 2)

        # 2) Pedido PENDIENTE y renglones en PostgreSQL (el stock se descuenta hasta que se paga)
        conn = get_db_connection()
        fila = conn.execute(
            "INSERT INTO pedidos (total, status, usuario_id, direccion_envio, metodo_pago) "
            "VALUES (%s, 'PENDIENTE', %s, %s, %s) RETURNING *",
            (total, usuario_id, datos.direccion_envio.strip(), datos.metodo_pago)
        ).fetchone()
        for producto_id, cantidad, precio in renglones:
            conn.execute(
                "INSERT INTO detalles_pedido (pedido_id, producto_id, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)",
                (fila["id"], producto_id, cantidad, precio)
            )
        conn.commit()
        conn.close()
        return fila_a_pedido(fila)

    # ---------------- PAYPAL ----------------

    @strawberry.mutation(description="Crea la orden en PayPal para un pedido pendiente. Regresa el orderID.",
                         permission_classes=[IsAuthenticated])
    def crear_orden_paypal(self, info: Info, pedido_id: int) -> str:
        conn = get_db_connection()
        try:
            r = pedido_pendiente_del_usuario(conn, pedido_id, info.context["user"], "PayPal")
            if r["status"] != "PENDIENTE":
                raise Exception("Este pedido ya no está pendiente de pago")
            return payments.paypal_crear_orden(r["id"], float(r["total"]))
        finally:
            conn.close()

    @strawberry.mutation(description="Cobra la orden aprobada en PayPal, verifica el monto y marca el pedido PAGADO",
                         permission_classes=[IsAuthenticated])
    def capturar_pago_paypal(self, info: Info, pedido_id: int, order_id: str) -> Pedido:
        conn = get_db_connection()
        try:
            r = pedido_pendiente_del_usuario(conn, pedido_id, info.context["user"], "PayPal")
            pago = payments.paypal_capturar(order_id)
            validar_monto(r, pago)
            if pago["status"] != "COMPLETED":
                raise Exception(f"PayPal reporta el pago como {pago['status']}")
            return marcar_pagado(conn, pedido_id, pago["capture_id"])
        finally:
            conn.close()

    # ---------------- MERCADO PAGO ----------------

    @strawberry.mutation(description="Crea la preferencia de Mercado Pago. Regresa la URL a donde se redirige al usuario.",
                         permission_classes=[IsAuthenticated])
    def crear_pago_mercado_pago(self, info: Info, pedido_id: int) -> str:
        conn = get_db_connection()
        try:
            r = pedido_pendiente_del_usuario(conn, pedido_id, info.context["user"], "Mercado Pago")
            if r["status"] != "PENDIENTE":
                raise Exception("Este pedido ya no está pendiente de pago")
            detalles = conn.execute(
                "SELECT producto_id, cantidad, precio_unitario FROM detalles_pedido WHERE pedido_id = %s",
                (pedido_id,)
            ).fetchall()
        finally:
            conn.close()

        col = get_mongo().productos
        items = []
        for d in detalles:
            p = col.find_one({"id": d["producto_id"]}) or {}
            items.append({
                "titulo": f'{p.get("nombre", "Producto")} - {p.get("artista", "")}',
                "cantidad": d["cantidad"],
                "precio": float(d["precio_unitario"]),
            })
        return payments.mp_crear_preferencia(pedido_id, items)

    @strawberry.mutation(description="Al regresar de Mercado Pago: consulta el pago real y marca el pedido PAGADO",
                         permission_classes=[IsAuthenticated])
    def confirmar_pago_mercado_pago(self, info: Info, pedido_id: int, payment_id: str) -> Pedido:
        conn = get_db_connection()
        try:
            r = pedido_pendiente_del_usuario(conn, pedido_id, info.context["user"], "Mercado Pago")
            pago = payments.mp_consultar_pago(payment_id)
            validar_monto(r, pago)
            if pago["status"] != "approved":
                raise Exception(f"Mercado Pago reporta el pago como '{pago['status']}'")
            return marcar_pagado(conn, pedido_id, str(payment_id))
        finally:
            conn.close()

    @strawberry.mutation(description="Botón 'Ya pagué': busca en Mercado Pago un pago aprobado del pedido y lo marca PAGADO",
                         permission_classes=[IsAuthenticated])
    def verificar_pago_mercado_pago(self, info: Info, pedido_id: int) -> Pedido:
        conn = get_db_connection()
        try:
            r = pedido_pendiente_del_usuario(conn, pedido_id, info.context["user"], "Mercado Pago")
            if r["status"] != "PENDIENTE":
                return fila_a_pedido(r)  # ya estaba pagado
            pago = payments.mp_buscar_pago_aprobado(pedido_id)
            if not pago:
                raise Exception("Todavía no vemos un pago aprobado en Mercado Pago. Termina de pagar y vuelve a intentar.")
            validar_monto(r, pago)
            return marcar_pagado(conn, pedido_id, pago["id"])
        finally:
            conn.close()

    # ---------------- ADMIN ----------------

    @strawberry.mutation(description="(Admin) Cambiar el estado de un pedido: ENVIADO, ENTREGADO, CANCELADO...",
                         permission_classes=[IsAdmin])
    def cambiar_status_pedido(self, id: int, status: str) -> Optional[Pedido]:
        if status not in STATUS_PEDIDO:
            raise Exception("Estado no válido")
        conn = get_db_connection()
        r = conn.execute("UPDATE pedidos SET status = %s WHERE id = %s RETURNING *", (status, id)).fetchone()
        conn.commit()
        conn.close()
        return fila_a_pedido(r) if r else None

schema = strawberry.Schema(query=Query, mutation=Mutation)