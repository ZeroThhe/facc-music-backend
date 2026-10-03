
-- BASE DE DATOS E-COMMERCE DE VINILOS - FACC MUSIC (UNIFICADO)
-- Proyecto Consolidado PWII (Práctica P2-6)


DROP TABLE IF EXISTS detalles_pedido;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS categorias;
DROP TABLE IF EXISTS usuarios;

-- 1. Tabla Categorías
CREATE TABLE categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    imagen VARCHAR(255)
);

-- 2. Tabla Productos
CREATE TABLE productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(150) NOT NULL,
    artista VARCHAR(150) NOT NULL,
    formato VARCHAR(50) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    imagen VARCHAR(500) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 15,
    destacado BOOLEAN NOT NULL DEFAULT 0,
    categoria_id INTEGER NOT NULL,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
);

-- 3. Tabla Usuarios
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'CLIENTE' CHECK(rol IN ('CLIENTE', 'ADMIN'))
);

-- 4. Tabla Pedidos (Órdenes de Compra)
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'COMPLETADO',
    usuario_id INTEGER NOT NULL,
    direccion_envio TEXT NOT NULL,
    metodo_pago VARCHAR(50) NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- 5. Tabla Detalles del Pedido (Renglones)
CREATE TABLE detalles_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);


-- DATOS SEMILLA (CATÁLOGO COMPLETO FACC MUSIC)


-- Categorías
INSERT INTO categorias (id, nombre, descripcion, imagen) VALUES
(1, 'Rock & Clásicos (LP)', 'Prensados audiófilos en acetato de 180g de leyendas del rock', 'https://images.unsplash.com/photo-1539375665275-f9de415ef9ac?w=600'),
(2, 'Pop & Hits (LP / CD)', 'Grandes producciones pop, melodías pegajosas y ediciones especiales', 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600'),
(3, 'K-Pop & Asian Pop', 'Ediciones especial boxset con fotolibros, tarjetas y coleccionables', 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600'),
(4, 'Hip-Hop & R&B (LP)', 'Álbumes icónicos del género en doble vinilo prensado pesado', 'https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=600'),
(5, 'Jazz, Blues & Soul', 'Interpretaciones acústicas cálidas, saxofón e impresiones de alta fidelidad', 'https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=600'),
(6, 'Metal & Alternative', 'Discos potentes de metal, grunge e indie rock alternativo', 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=600');

-- Productos (24 títulos)
INSERT INTO productos (id, nombre, artista, formato, precio, imagen, stock, destacado, categoria_id) VALUES
(1, 'The Dark Side of the Moon', 'Pink Floyd', 'Vinilo 180g Remastered', 850.00, 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=600', 20, 1, 1),
(2, 'Abbey Road (Edición 50 Aniversario)', 'The Beatles', 'Vinilo 180g', 899.00, 'https://images.unsplash.com/photo-1539375665275-f9de415ef9ac?w=600', 15, 1, 1),
(3, 'Rumours (Edición Limitada)', 'Fleetwood Mac', 'Vinilo Transparente', 700.00, 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600', 12, 0, 1),
(4, 'Led Zeppelin IV', 'Led Zeppelin', 'Vinilo 180g Remaster', 660.00, 'https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=600', 18, 0, 1),

(5, '1989 (Taylor Version)', 'Taylor Swift', '2LP Crystal Pink', 980.00, 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600', 25, 1, 2),
(6, 'Future Nostalgia (Moonlight Edition)', 'Dua Lipa', 'Vinilo Neon Pink', 700.00, 'https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=600', 14, 0, 2),
(7, 'Random Access Memories (10th Anniversary)', 'Daft Punk', 'CD Deluxe 2-Disc', 499.00, 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600', 30, 1, 2),
(8, 'Fine Line', 'Harry Styles', '2LP Vinilo Negro', 790.00, 'https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=600', 16, 0, 2),

(9, 'PROOF (Standard Edition)', 'BTS', '3CD BoxSet Deluxe', 1350.00, 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600', 10, 1, 3),
(10, 'BORN PINK', 'BLACKPINK', 'Target Exclusive CD', 570.00, 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600', 15, 0, 3),
(11, 'Get Up (Bunny Beach Bag Ver.)', 'NewJeans', 'CD Boxset Special', 640.00, 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=600', 12, 1, 3),
(12, 'MAXIDENT (Limited Edition)', 'Stray Kids', 'CD + Photobook', 540.00, 'https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=600', 20, 0, 3),

(13, 'To Pimp a Butterfly', 'Kendrick Lamar', '2LP Vinilo 180g', 840.00, 'https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=600', 14, 1, 4),
(14, 'Blonde (Official Repress)', 'Frank Ocean', '2LP Vinilo Negro', 1300.00, 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600', 8, 1, 4),
(15, 'IGOR', 'Tyler, The Creator', 'Vinilo Verde Menta', 730.00, 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600', 11, 0, 4),
(16, 'The College Dropout', 'Kanye West', '2LP Gatefold', 760.00, 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=600', 16, 0, 4),

(17, 'Kind of Blue', 'Miles Davis', 'Vinilo Audiófilo 180g', 860.00, 'https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=600', 8, 1, 5),
(18, 'A Love Supreme', 'John Coltrane', 'Vinilo Impulse 180g', 790.00, 'https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=600', 10, 0, 5),
(19, 'At Last! (Edición Especial)', 'Etta James', 'Vinilo Azul Translúcido', 560.00, 'https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=600', 9, 0, 5),
(20, 'Blue Train (Tone Poet Series)', 'John Coltrane', 'Vinilo Audiófilo LP', 900.00, 'https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=600', 7, 0, 5),

(21, 'Master of Puppets (Remastered)', 'Metallica', 'Vinilo 180g Heavy', 640.00, 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=600', 22, 1, 6),
(22, 'Nevermind (30th Anniversary)', 'Nirvana', 'Vinilo LP + 7 inch', 690.00, 'https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=600', 17, 1, 6),
(23, 'OK Computer (OKNOTOK 1997-2017)', 'Radiohead', '3LP 180g Box', 920.00, 'https://images.unsplash.com/photo-1539375665275-f9de415ef9ac?w=600', 13, 0, 6),
(24, 'Toxicity', 'System Of A Down', 'Vinilo Heavyweight', 580.00, 'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=600', 19, 0, 6);

-- Usuarios
INSERT INTO usuarios (id, nombre, email, password, rol) VALUES
(1, 'Fátima Martín del Campo', 'fatima.martin@facc.music', 'facc2026', 'ADMIN'),
(2, 'Cliente Ejemplo', 'cliente@correo.com', 'cliente123', 'CLIENTE');

-- Pedidos Ejemplo
INSERT INTO pedidos (id, fecha, total, status, usuario_id, direccion_envio, metodo_pago) VALUES
(1, '2026-09-15 11:20:00', 1349.00, 'COMPLETADO', 1, 'Av. Universidad #1020, Guadalajara, JAL', 'Tarjeta de Crédito'),
(2, '2026-09-17 16:45:00', 1350.00, 'COMPLETADO', 2, 'Calle Reforma #45, Zapopan, JAL', 'PayPal');

INSERT INTO detalles_pedido (id, pedido_id, producto_id, cantidad, precio_unitario) VALUES
(1, 1, 1, 1, 850.00),
(2, 1, 7, 1, 499.00),
(3, 2, 9, 1, 1350.00);
