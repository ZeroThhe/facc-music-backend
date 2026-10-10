-- BASE DE DATOS FACC MUSIC - PARTE RELACIONAL (PostgreSQL)
-- Usuarios, pedidos y renglones de pedido.
-- El catálogo (categorías y productos) vive en MongoDB (ver catalogo.json).

DROP TABLE IF EXISTS detalles_pedido;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS usuarios;

-- 1. Tabla Usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'CLIENTE' CHECK (rol IN ('CLIENTE', 'ADMIN'))
);

-- 2. Tabla Pedidos (Órdenes de Compra)
CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    direccion_envio TEXT NOT NULL,
    metodo_pago VARCHAR(50) NOT NULL,
    referencia_pago VARCHAR(100)
);

-- 3. Tabla Detalles del Pedido (Renglones)
-- producto_id apunta al campo "id" de la colección productos en MongoDB
CREATE TABLE detalles_pedido (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario NUMERIC(10, 2) NOT NULL
);

-- DATOS SEMILLA
-- (las contraseñas se convierten a bcrypt al arrancar el servidor)
INSERT INTO usuarios (id, nombre, email, password, rol) VALUES
(1, 'Fátima Martín del Campo', 'fatima.martin@facc.music', 'facc2026', 'ADMIN'),
(2, 'Cliente Ejemplo', 'cliente@correo.com', 'cliente123', 'CLIENTE');

INSERT INTO pedidos (id, fecha, total, status, usuario_id, direccion_envio, metodo_pago) VALUES
(1, '2026-09-15 11:20:00', 1349.00, 'COMPLETADO', 1, 'Av. Universidad #1020, Guadalajara, JAL', 'Tarjeta de Crédito'),
(2, '2026-09-17 16:45:00', 1350.00, 'COMPLETADO', 2, 'Calle Reforma #45, Zapopan, JAL', 'PayPal');

INSERT INTO detalles_pedido (id, pedido_id, producto_id, cantidad, precio_unitario) VALUES
(1, 1, 1, 1, 850.00),
(2, 1, 7, 1, 499.00),
(3, 2, 9, 1, 1350.00);

-- Como insertamos con id fijo, movemos los contadores SERIAL al siguiente número libre
SELECT setval('usuarios_id_seq', (SELECT MAX(id) FROM usuarios));
SELECT setval('pedidos_id_seq', (SELECT MAX(id) FROM pedidos));
SELECT setval('detalles_pedido_id_seq', (SELECT MAX(id) FROM detalles_pedido));
