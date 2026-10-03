"""
Schema SDL GraphQL para FACC Music (PWII - Práctica P2-6)
Materia: Programación Web 2 · Profesor: Kegovc
Alumna: Fátima Martín del Campo Castellanos (22300884)
"""

import enum
from typing import List, Optional
import strawberry
from strawberry.types import Info
from database import get_db_connection
from auth import hash_password, IsAuthenticated, IsAdmin


# ENUMS Y TIPOS AUXILIARES


@strawberry.enum
class RolEnum(enum.Enum):
    CLIENTE = "CLIENTE"
    ADMIN = "ADMIN"


# TIPOS GRAPHQL (ENTIDADES CON RESOLUTORES ANIDADOS)


@strawberry.type(description="Entidad Categoría con relación a sus Productos")
class Categoria:
    id: int
    nombre: str
    descripcion: Optional[str]
    imagen: Optional[str]

    @strawberry.field(description="Resolutor anidado: Obtener los productos de esta categoría")
    def productos(self) -> List["Producto"]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE categoria_id = ?", (self.id,))
        rows = cursor.fetchall()
        conn.close()
        return [
            Producto(
                id=r["id"],
                nombre=r["nombre"],
                artista=r["artista"],
                formato=r["formato"],
                precio=float(r["precio"]),
                imagen=r["imagen"],
                stock=r["stock"],
                destacado=bool(r["destacado"]),
                categoria_id=r["categoria_id"]
            )
            for r in rows
        ]

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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categorias WHERE id = ?", (self.categoria_id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return Categoria(
                id=r["id"],
                nombre=r["nombre"],
                descripcion=r["descripcion"],
                imagen=r["imagen"]
            )
        return None

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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = ?", (self.producto_id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return Producto(
                id=r["id"],
                nombre=r["nombre"],
                artista=r["artista"],
                formato=r["formato"],
                precio=float(r["precio"]),
                imagen=r["imagen"],
                stock=r["stock"],
                destacado=bool(r["destacado"]),
                categoria_id=r["categoria_id"]
            )
        return None

@strawberry.type(description="Entidad Pedido (Orden de Compra)")
class Pedido:
    id: int
    fecha: str
    total: float
    status: str
    usuario_id: int
    direccion_envio: str
    metodo_pago: str

    @strawberry.field(description="Resolutor anidado: Usuario que realizó el pedido")
    def usuario(self) -> Optional[Usuario]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id = ?", (self.usuario_id,))
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
        cursor.execute("SELECT * FROM detalles_pedido WHERE pedido_id = ?", (self.id,))
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

@strawberry.input(description="Renglón del carrito para registrar en un pedido")
class DetalleInput:
    producto_id: int
    cantidad: int
    precio_unitario: float

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


# OPERACIONES DE LECTURA (QUERIES)


@strawberry.type
class Query:
    @strawberry.field(description="Listar todas las categorías con sus productos anidados")
    def categorias(self) -> List[Categoria]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categorias")
        rows = cursor.fetchall()
        conn.close()
        return [
            Categoria(
                id=r["id"],
                nombre=r["nombre"],
                descripcion=r["descripcion"],
                imagen=r["imagen"]
            )
            for r in rows
        ]

    @strawberry.field(description="Consultar una categoría por su ID")
    def categoria(self, id: int) -> Optional[Categoria]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categorias WHERE id = ?", (id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return Categoria(
                id=r["id"],
                nombre=r["nombre"],
                descripcion=r["descripcion"],
                imagen=r["imagen"]
            )
        return None

    @strawberry.field(description="Listar el catálogo de productos con paginación y filtros por categoría o búsqueda")
    def productos(
        self,
        limit: Optional[int] = 20,
        offset: Optional[int] = 0,
        categoriaId: Optional[int] = None,
        busqueda: Optional[str] = None
    ) -> ProductoPaginado:
        conn = get_db_connection()
        cursor = conn.cursor()

        query_sql = "SELECT * FROM productos WHERE 1=1"
        count_sql = "SELECT COUNT(*) as total FROM productos WHERE 1=1"
        params = []

        if categoriaId:
            query_sql += " AND categoria_id = ?"
            count_sql += " AND categoria_id = ?"
            params.append(categoriaId)

        if busqueda:
            query_sql += " AND (nombre LIKE ? OR artista LIKE ?)"
            count_sql += " AND (nombre LIKE ? OR artista LIKE ?)"
            search_param = f"%{busqueda}%"
            params.extend([search_param, search_param])

        cursor.execute(count_sql, params)
        total = cursor.fetchone()["total"]

        query_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query_sql, params)
        rows = cursor.fetchall()
        conn.close()

        lista_prods = [
            Producto(
                id=r["id"],
                nombre=r["nombre"],
                artista=r["artista"],
                formato=r["formato"],
                precio=float(r["precio"]),
                imagen=r["imagen"],
                stock=r["stock"],
                destacado=bool(r["destacado"]),
                categoria_id=r["categoria_id"]
            )
            for r in rows
        ]
        return ProductoPaginado(total=total, productos=lista_prods)

    @strawberry.field(description="Consultar un producto específico por ID")
    def producto(self, id: int) -> Optional[Producto]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = ?", (id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return Producto(
                id=r["id"],
                nombre=r["nombre"],
                artista=r["artista"],
                formato=r["formato"],
                precio=float(r["precio"]),
                imagen=r["imagen"],
                stock=r["stock"],
                destacado=bool(r["destacado"]),
                categoria_id=r["categoria_id"]
            )
        return None

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
            cursor.execute("SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY fecha DESC", (user["id"],))
        rows = cursor.fetchall()
        conn.close()
        return [
            Pedido(
                id=r["id"],
                fecha=r["fecha"],
                total=float(r["total"]),
                status=r["status"],
                usuario_id=r["usuario_id"],
                direccion_envio=r["direccion_envio"],
                metodo_pago=r["metodo_pago"]
            )
            for r in rows
        ]


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
                "INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, 'CLIENTE')",
                (datos.nombre.strip(), email, hash_password(datos.password))
            )
            conn.commit()
        except Exception:
            conn.close()
            raise Exception("Ese correo ya está registrado")

        uid = cur.lastrowid
        conn.close()
        return Usuario(id=uid, nombre=datos.nombre.strip(), email=email, rol=RolEnum.CLIENTE)

    @strawberry.mutation(description="Registrar un nuevo producto en el catálogo", permission_classes=[IsAdmin])
    def registrar_producto(self, input: ProductoInput) -> Producto:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO productos (nombre, artista, formato, precio, imagen, stock, destacado, categoria_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (input.nombre, input.artista, input.formato, input.precio, input.imagen, input.stock, int(input.destacado), input.categoria_id)
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE productos
            SET nombre=?, artista=?, formato=?, precio=?, imagen=?, stock=?, destacado=?, categoria_id=?
            WHERE id=?
            """,
            (input.nombre, input.artista, input.formato, input.precio, input.imagen, input.stock, int(input.destacado), input.categoria_id, id)
        )
        conn.commit()
        conn.close()
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM productos WHERE id = ?", (id,))
        rows_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_deleted > 0

    @strawberry.mutation(
        description="Registrar un pedido completo con sus renglones del carrito",
        permission_classes=[IsAuthenticated]
    )
    def registrar_pedido(self, info: Info, datos: PedidoInput) -> Pedido:
        usuario_id = info.context["user"]["id"]
        conn = get_db_connection()
        cursor = conn.cursor()

        total = sum(d.cantidad * d.precio_unitario for d in datos.detalles)

        cursor.execute(
            """
            INSERT INTO pedidos (total, status, usuario_id, direccion_envio, metodo_pago)
            VALUES (?, 'COMPLETADO', ?, ?, ?)
            """,
            (total, usuario_id, datos.direccion_envio, datos.metodo_pago)
        )
        pedido_id = cursor.lastrowid

        for d in datos.detalles:
            cursor.execute(
                """
                INSERT INTO detalles_pedido (pedido_id, producto_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
                """,
                (pedido_id, d.producto_id, d.cantidad, d.precio_unitario)
            )
            cursor.execute(
                "UPDATE productos SET stock = MAX(0, stock - ?) WHERE id = ?",
                (d.cantidad, d.producto_id)
            )

        conn.commit()

        cursor.execute("SELECT fecha FROM pedidos WHERE id = ?", (pedido_id,))
        fecha = cursor.fetchone()["fecha"]
        conn.close()

        return Pedido(
            id=pedido_id,
            fecha=fecha,
            total=total,
            status="COMPLETADO",
            usuario_id=usuario_id,
            direccion_envio=datos.direccion_envio,
            metodo_pago=datos.metodo_pago
        )

schema = strawberry.Schema(query=Query, mutation=Mutation)