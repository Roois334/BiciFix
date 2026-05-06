-- ═══════════════════════════════════════════════════════════════════
--  BICIFIX — Base de Datos Completa v5
--  Cundinamarca: Facatativa · Madrid · Mosquera
--  25 ordenes con datos realistas para reportes
--  Motor: MySQL 8.0+  |  Charset: utf8mb4
-- ═══════════════════════════════════════════════════════════════════
--  CREDENCIALES:
--  Admin    : admin@bicifix.com   / admin123
--  Mecanicos: (ver tabla)         / mecanico123
--  Clientes : (ver tabla)         / cliente123
-- ═══════════════════════════════════════════════════════════════════

DROP DATABASE IF EXISTS bicifix;
CREATE DATABASE bicifix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bicifix;

-- ── TABLA: usuarios ──────────────────────────────────────────────
CREATE TABLE usuarios (
    id             INT          PRIMARY KEY AUTO_INCREMENT,
    nombre         VARCHAR(80)  NOT NULL,
    apellido       VARCHAR(80)  NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    password       VARCHAR(255) NOT NULL,
    telefono       VARCHAR(20),
    ciudad         VARCHAR(80),
    rol            ENUM('admin','mecanico','cliente') NOT NULL DEFAULT 'cliente',
    activo         TINYINT(1)   NOT NULL DEFAULT 1,
    fecha_registro DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: mecanicos ─────────────────────────────────────────────
CREATE TABLE mecanicos (
    id                    INT          PRIMARY KEY AUTO_INCREMENT,
    usuario_id            INT          NOT NULL,
    zona                  VARCHAR(100),
    certificaciones       TEXT,
    calificacion_promedio DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    total_servicios       INT          NOT NULL DEFAULT 0,
    estado_mecanico       ENUM('disponible','ocupado','inactivo') NOT NULL DEFAULT 'disponible',
    fecha_ingreso         DATE,
    notas_admin           TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: bicicletas ────────────────────────────────────────────
CREATE TABLE bicicletas (
    id          INT         PRIMARY KEY AUTO_INCREMENT,
    cliente_id  INT         NOT NULL,
    marca       VARCHAR(80) NOT NULL,
    modelo      VARCHAR(80),
    color       VARCHAR(40),
    tipo        ENUM('Urbana','MTB','Ruta','BMX','Electrica','Otra') DEFAULT 'Urbana',
    anio        YEAR,
    descripcion TEXT,
    FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: servicios ─────────────────────────────────────────────
CREATE TABLE servicios (
    id              INT           PRIMARY KEY AUTO_INCREMENT,
    nombre          VARCHAR(120)  NOT NULL,
    descripcion     TEXT,
    icono           VARCHAR(10)   DEFAULT '',
    categoria       VARCHAR(60)   DEFAULT 'General',
    precio_min      DECIMAL(10,2) NOT NULL DEFAULT 10.00,
    precio_max      DECIMAL(10,2) NOT NULL DEFAULT 50.00,
    tiempo_estimado VARCHAR(40)   DEFAULT '60 min',
    activo          TINYINT(1)    NOT NULL DEFAULT 1,
    fecha_creacion  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: talleres ──────────────────────────────────────────────
CREATE TABLE talleres (
    id             INT           PRIMARY KEY AUTO_INCREMENT,
    nombre         VARCHAR(120)  NOT NULL,
    descripcion    TEXT,
    direccion      VARCHAR(255)  NOT NULL,
    ciudad         VARCHAR(80)   NOT NULL DEFAULT 'Facatativa',
    barrio         VARCHAR(100),
    telefono       VARCHAR(20),
    email          VARCHAR(120),
    horario        VARCHAR(120)  DEFAULT 'Lun-Sab 8:00am-6:00pm',
    lat            DECIMAL(10,7),
    lng            DECIMAL(10,7),
    calificacion   DECIMAL(3,2)  NOT NULL DEFAULT 0.00,
    total_resenas  INT           NOT NULL DEFAULT 0,
    activo         TINYINT(1)    NOT NULL DEFAULT 1,
    fecha_creacion DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: taller_mecanicos ──────────────────────────────────────
CREATE TABLE taller_mecanicos (
    taller_id   INT NOT NULL,
    mecanico_id INT NOT NULL,
    PRIMARY KEY (taller_id, mecanico_id),
    FOREIGN KEY (taller_id)   REFERENCES talleres(id)  ON DELETE CASCADE,
    FOREIGN KEY (mecanico_id) REFERENCES usuarios(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: taller_servicios ──────────────────────────────────────
CREATE TABLE taller_servicios (
    taller_id   INT NOT NULL,
    servicio_id INT NOT NULL,
    PRIMARY KEY (taller_id, servicio_id),
    FOREIGN KEY (taller_id)   REFERENCES talleres(id)  ON DELETE CASCADE,
    FOREIGN KEY (servicio_id) REFERENCES servicios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: ordenes ───────────────────────────────────────────────
CREATE TABLE ordenes (
    id                     INT           PRIMARY KEY AUTO_INCREMENT,
    cliente_id             INT           NOT NULL,
    mecanico_id            INT           DEFAULT NULL,
    servicio_id            INT           NOT NULL,
    bici_id                INT           DEFAULT NULL,
    descripcion_problema   TEXT,
    ubicacion              VARCHAR(255),
    fecha_solicitud        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_servicio         DATETIME,
    precio_final           DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado                 ENUM('pendiente','asignada','en_camino','proceso','completada','cancelada') NOT NULL DEFAULT 'pendiente',
    tipo_atencion          ENUM('taller','domicilio','recogida') DEFAULT 'taller',
    observaciones_mecanico TEXT,
    emergencia             TINYINT(1)    NOT NULL DEFAULT 0,
    FOREIGN KEY (cliente_id)  REFERENCES usuarios(id)   ON DELETE RESTRICT  ON UPDATE CASCADE,
    FOREIGN KEY (mecanico_id) REFERENCES usuarios(id)   ON DELETE SET NULL   ON UPDATE CASCADE,
    FOREIGN KEY (servicio_id) REFERENCES servicios(id)  ON DELETE RESTRICT   ON UPDATE CASCADE,
    FOREIGN KEY (bici_id)     REFERENCES bicicletas(id) ON DELETE SET NULL   ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: calificaciones ────────────────────────────────────────
CREATE TABLE calificaciones (
    id          INT      PRIMARY KEY AUTO_INCREMENT,
    orden_id    INT      NOT NULL UNIQUE,
    mecanico_id INT      DEFAULT NULL,
    cliente_id  INT      NOT NULL,
    puntuacion  TINYINT  NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
    comentario  TEXT,
    fecha       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (orden_id)    REFERENCES ordenes(id)  ON DELETE CASCADE   ON UPDATE CASCADE,
    FOREIGN KEY (mecanico_id) REFERENCES usuarios(id) ON DELETE SET NULL  ON UPDATE CASCADE,
    FOREIGN KEY (cliente_id)  REFERENCES usuarios(id) ON DELETE CASCADE   ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── TABLA: notificaciones ────────────────────────────────────────
CREATE TABLE notificaciones (
    id         INT         PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT         NOT NULL,
    tipo       VARCHAR(40) DEFAULT 'info',
    titulo     VARCHAR(120),
    mensaje    TEXT,
    leida      TINYINT(1)  NOT NULL DEFAULT 0,
    fecha      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── INDICES ──────────────────────────────────────────────────────
CREATE INDEX idx_ord_cliente   ON ordenes(cliente_id);
CREATE INDEX idx_ord_mecanico  ON ordenes(mecanico_id);
CREATE INDEX idx_ord_estado    ON ordenes(estado);
CREATE INDEX idx_ord_fecha     ON ordenes(fecha_solicitud);
CREATE INDEX idx_bici_cliente  ON bicicletas(cliente_id);
CREATE INDEX idx_cal_mecanico  ON calificaciones(mecanico_id);
CREATE INDEX idx_notif_usuario ON notificaciones(usuario_id, leida);

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: USUARIOS
-- Todos los mecanicos: mecanico123
-- Todos los clientes : cliente123
-- Admin              : admin123
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO usuarios (id,nombre,apellido,email,password,telefono,ciudad,rol,activo) VALUES

-- ADMIN (admin123)
(1,'Admin','BiciFix','admin@bicifix.com',
 'scrypt:32768:8:1$tWDu3pxPpImOXNwZ$7553fd4599b2560c332475a3a108faff6f7e2195b42d1de4fad57ed8d5efc0cdc75ca9396cd20b12f52b1b8f4e0664a1dbbd6c637f4c49c771b7e277e3826310',
 '3001000000','Facatativa','admin',1),

-- MECANICOS TALLER 1 — CicloVia Facatativa (mecanico123)
(2,'Carlos','Ramirez','carlos@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3112233445','Facatativa','mecanico',1),
(3,'Diana','Salcedo','diana@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3113344556','Facatativa','mecanico',1),

-- MECANICOS TALLER 2 — Rueda y Pedal Madrid (mecanico123)
(4,'Andres','Torres','andres@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3124455667','Madrid','mecanico',1),
(5,'Felipe','Castillo','felipe@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3135566778','Madrid','mecanico',1),

-- MECANICOS TALLER 3 — Taller del Ciclista Mosquera (mecanico123)
(6,'Sergio','Mendoza','sergio@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3146677889','Mosquera','mecanico',1),
(7,'Laura','Jimenez','laura@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3157788990','Mosquera','mecanico',1),

-- MECANICOS TALLER 4 — Bici Center Facatativa (mecanico123)
(8,'Luis','Moreno','luis@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3168899001','Facatativa','mecanico',1),
(9,'Camila','Ospina','camila@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3179900112','Facatativa','mecanico',1),

-- MECANICOS TALLER 5 — Transmision Madrid (mecanico123)
(10,'Hector','Vargas','hector@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3180011223','Madrid','mecanico',1),
(11,'Paola','Rios','paola@bicifix.com',
 'scrypt:32768:8:1$p0qeurCM3ZZT4l4a$39e6b9c0704ac0a9bcc22c6305eb61610daa75065161df555328d9fb47a654217b2a95c4e951440812aa1774d96e75dd951ed22cafc17e9724a43917a80a9012',
 '3191122334','Madrid','mecanico',1),

-- CLIENTES (cliente123)
(12,'Juan','Perez','juan@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3202233445','Facatativa','cliente',1),
(13,'Maria','Lopez','maria@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3213344556','Madrid','cliente',1),
(14,'Pedro','Gomez','pedro@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3224455667','Mosquera','cliente',1),
(15,'Ana','Martinez','ana@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3235566778','Facatativa','cliente',1),
(16,'Santiago','Vargas','santiago@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3246677889','Madrid','cliente',1),
(17,'Valentina','Castro','valentina@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3257788990','Mosquera','cliente',1),
(18,'Andres','Herrera','andresher@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3268899001','Facatativa','cliente',1),
(19,'Luisa','Fernandez','luisa@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3279900112','Madrid','cliente',1),
(20,'Camilo','Rojas','camilo@gmail.com',
 'scrypt:32768:8:1$kN4NDVxPRMlf3XU1$268d522b65a4325cc2bff3929c3c51ad15fc3409e95ea4e6f024903bf9af08e7ba649c0195619465326c4007cff1fa7e9b6e365cc2e5432158a4927ad53e4097',
 '3280011223','Mosquera','cliente',1);

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: PERFILES MECANICOS
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO mecanicos (usuario_id,zona,certificaciones,calificacion_promedio,total_servicios,estado_mecanico,fecha_ingreso) VALUES
(2,'Facatativa Centro','Certificado en mecanica MTB y Ruta, 5 anos de experiencia',4.80,0,'disponible','2024-01-15'),
(3,'Facatativa Sur','Especialista en frenos de disco hidraulicos y suspension',4.65,0,'disponible','2024-06-01'),
(4,'Madrid Centro','Especialista en bicicletas electricas y transmision Shimano Di2',4.70,0,'disponible','2024-03-10'),
(5,'Madrid Norte','Mecanico general, reparaciones rapidas en via y parchados',4.40,0,'disponible','2024-08-20'),
(6,'Mosquera Centro','Certificado SENA, especialidad en centrado de ruedas',4.90,0,'disponible','2023-09-05'),
(7,'Mosquera Sur','Experta en ajuste de precision y bicicletas de ruta de carbono',4.75,0,'ocupado','2024-02-18'),
(8,'Facatativa Occidente','Certificado SENA, frenos de disco y suspension completa',4.85,0,'disponible','2023-11-20'),
(9,'Facatativa Norte','Especialista en bicicletas de grava y cicloturismo',4.60,0,'disponible','2024-04-12'),
(10,'Madrid Sur','Dominio de transmisiones SRAM y Campagnolo, 6 anos',4.55,0,'disponible','2023-07-30'),
(11,'Madrid Centro','Tecnico en bicicletas electricas Bosch y Shimano Steps',4.45,0,'disponible','2024-09-01');

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: SERVICIOS
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO servicios (id,nombre,descripcion,icono,categoria,precio_min,precio_max,tiempo_estimado,activo) VALUES
(1,'Mantenimiento preventivo basico','Limpieza general, lubricacion de cadena, revision y ajuste basico de frenos y cambios.','','Mantenimiento',25000,40000,'60 min',1),
(2,'Mantenimiento preventivo completo','Desmontaje parcial, limpieza profunda, lubricacion integral y ajuste preciso.','','Mantenimiento',55000,85000,'90 min',1),
(3,'Parchado de llanta','Localizacion del pinchazo y aplicacion de parche vulcanizado de alta resistencia.','','Reparacion',10000,18000,'30 min',1),
(4,'Cambio de camara de aire','Desmontaje y reemplazo de camara danada por nueva.','','Reparacion',15000,30000,'30 min',1),
(5,'Cambio de llanta completa','Reemplazo de cubierta exterior por desgaste excesivo o dano irreparable.','','Reparacion',25000,60000,'30 min',1),
(6,'Ajuste de frenos','Calibracion precisa de frenos delanteros y traseros. Incluye cable si es necesario.','','Ajuste',15000,30000,'30 min',1),
(7,'Ajuste de cambios y transmision','Calibracion de descarriladores, tension de cables y palancas de cambio.','','Ajuste',20000,40000,'60 min',1),
(8,'Cambio de cable de freno o cambio','Reemplazo de cable desgastado o roto. Incluye funda si esta deteriorada.','','Reparacion',18000,35000,'30 min',1),
(9,'Centrado de rueda','Correccion de tension de rayos para rueda perfectamente recta.','','Ajuste',20000,40000,'60 min',1),
(10,'Revision tecnica completa','Diagnostico integral con informe detallado del estado de cada componente.','','Diagnostico',30000,50000,'60 min',1),
(11,'Limpieza y lubricacion de cadena','Desengrase profundo, limpieza de platos y pinones, lubricacion especifica.','','Mantenimiento',12000,20000,'30 min',1),
(12,'Ajuste de manubrio y potencia','Reposicionamiento del manubrio a postura correcta del ciclista.','','Ajuste',12000,22000,'30 min',1),
(13,'Ajuste de sillin y tija','Regulacion precisa de altura y posicion del sillin para postura ergonomica.','','Ajuste',8000,15000,'30 min',1),
(14,'Atencion de emergencia en via','Servicio inmediato donde fallo la bicicleta. Cargo adicional por desplazamiento.','','Emergencia',30000,60000,'60 min',1),
(15,'Instalacion de accesorios','Instalacion profesional de luces, guardabarros, portaequipaje u otros accesorios.','','Instalacion',15000,35000,'30 min',1);

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: TALLERES (Cundinamarca)
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO talleres (id,nombre,descripcion,direccion,ciudad,barrio,telefono,email,horario,lat,lng,calificacion,total_resenas,activo) VALUES
(1,'CicloVia Facatativa','Taller especializado en MTB y bicicletas de ruta con herramientas profesionales y repuestos originales.','Cra 3 # 8-25 Centro','Facatativa','Centro','314-555-0101','info@cicloviafacatativa.com','Lun-Sab 8:00am-6:00pm',4.8143200,-74.3549700,4.80,42,1),
(2,'Rueda y Pedal Madrid','Especialistas en bicicletas electricas, transmisiones Shimano y reparaciones rapidas.','Cll 5 # 4-18 El Centro','Madrid','El Centro','311-555-0202','contacto@ruedapedalmadrid.com','Lun-Sab 8:00am-6:30pm',4.7339400,-74.2647200,4.70,28,1),
(3,'Taller del Ciclista Mosquera','El taller mas completo de Mosquera. Mecanicos certificados SENA con experiencia en toda clase de bicicletas.','Cra 2 # 12-40 Zona Comercial','Mosquera','Zona Comercial','315-555-0303','taller@ciclista-mosquera.com','Lun-Dom 7:00am-7:00pm',4.7062500,-74.2313900,4.90,61,1),
(4,'Bici Center Facatativa','Especializado en bicicletas de grava, cicloturismo y MTB de alta gama. Diagnostico digital.','Cll 11 # 7-32 El Lago','Facatativa','El Lago','316-555-0404','bicicenter@facatativa.com','Lun-Sab 9:00am-6:00pm',4.8198600,-74.3489500,4.70,35,1),
(5,'Transmision Madrid','Especializado en transmisiones de precision, bicicletas electricas Bosch y Shimano Steps.','Cra 6 # 9-15 Via Bogota','Madrid','Via Bogota','317-555-0505','info@transmisionmadrid.com','Lun-Sab 8:00am-6:00pm',4.7285100,-74.2598300,4.50,19,1);

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: MECANICOS POR TALLER
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO taller_mecanicos (taller_id, mecanico_id) VALUES
(1,2),(1,3),   -- CicloVia Facatativa
(2,4),(2,5),   -- Rueda y Pedal Madrid
(3,6),(3,7),   -- Taller del Ciclista Mosquera
(4,8),(4,9),   -- Bici Center Facatativa
(5,10),(5,11); -- Transmision Madrid

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: TODOS LOS SERVICIOS A TODOS LOS TALLERES
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO taller_servicios (taller_id, servicio_id)
SELECT t.id, s.id FROM talleres t CROSS JOIN servicios s WHERE s.activo = 1;

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: BICICLETAS
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO bicicletas (id,cliente_id,marca,modelo,color,tipo,anio,descripcion) VALUES
(1,12,'Trek','FX3','Negro mate','Urbana',2022,'Bicicleta de ciudad para uso diario en Facatativa'),
(2,12,'Specialized','Rockhopper','Rojo y negro','MTB',2021,'MTB para rutas recreativas de fin de semana'),
(3,13,'Giant','Escape 3','Blanco perla','Urbana',2023,'Bicicleta ligera para moverse por Madrid'),
(4,14,'Merida','Crossway 20','Azul metalico','Urbana',2020,'Commuter diario en Mosquera'),
(5,15,'Cannondale','Topstone','Verde oliva','Ruta',2023,'Bicicleta de grava para cicloturismo Cundinamarca'),
(6,16,'Scott','Aspect 960','Negro y verde','MTB',2022,'MTB hardtail para rutas de montana'),
(7,17,'Bianchi','Via Nirone 7','Celeste azul','Ruta',2021,'Bicicleta de ruta para entrenamiento'),
(8,18,'Giant','Talon 3','Gris carbono','MTB',2020,'MTB para trails de fin de semana'),
(9,19,'Trek','Marlin 5','Azul marino','MTB',2022,'MTB para rutas largas en Cundinamarca'),
(10,20,'Specialized','Sirrus','Amarillo neon','Urbana',2023,'Bicicleta urbana commuter diaria');

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: 25 ORDENES
-- 20 completadas (historico de reportes) + 5 activas (pendiente/proceso)
-- Repartidas en los ultimos 5 meses para graficas mensuales
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO ordenes
  (id,cliente_id,mecanico_id,servicio_id,bici_id,descripcion_problema,ubicacion,
   fecha_solicitud,fecha_servicio,precio_final,estado,tipo_atencion,observaciones_mecanico,emergencia)
VALUES

-- ── ENERO 2026 ───────────────────────────────────────────────────
(1, 12,2,1,1,'Mantenimiento mensual, la cadena empieza a chiriar.',
 'CicloVia Facatativa','2026-01-08 09:00:00','2026-01-08 10:00:00',
 32500,'completada','taller','Cadena lubricada, frenos ajustados y llantas infladas. Bicicleta en excelente estado.',0),

(2, 13,4,6,3,'Freno delantero no jala bien, me da miedo bajar pendientes.',
 'Rueda y Pedal Madrid','2026-01-12 11:00:00','2026-01-12 11:45:00',
 22000,'completada','taller','Cable de freno delantero reemplazado. Sistema calibrado correctamente.',0),

(3, 14,6,3,4,'Llanta trasera pinchada en la via principal de Mosquera.',
 'Via Principal Mosquera Km 2','2026-01-15 08:30:00','2026-01-15 09:00:00',
 13000,'completada','domicilio','Pinchazo localizado y parche vulcanizado aplicado. Cliente satisfecho.',1),

(4, 15,8,10,5,'Quiero una revision completa antes de mi ruta de enero por Cundinamarca.',
 'Bici Center Facatativa','2026-01-20 10:00:00','2026-01-20 11:30:00',
 40000,'completada','taller','Revision integral realizada. Cadena con 40% de vida util. Frenos y transmision en buen estado.',0),

(5, 16,6,7,6,'Los cambios no entran bien, especialmente al tercer plato.',
 'Taller del Ciclista Mosquera','2026-01-25 14:00:00','2026-01-25 14:50:00',
 30000,'completada','taller','Descarrilador trasero ajustado, cable de cambio reemplazado. Perfecta calibracion.',0),

-- ── FEBRERO 2026 ─────────────────────────────────────────────────
(6, 17,7,2,7,'Mantenimiento profundo, 8 meses sin revision general.',
 'Taller del Ciclista Mosquera','2026-02-03 09:00:00','2026-02-03 10:45:00',
 70000,'completada','taller','Desmontaje parcial realizado. Rodamientos de pedivela limpiados. Todo en orden.',0),

(7, 18,2,4,8,'Camara de aire trasera reventada, quedo completamente desinflada.',
 'Cra 3 Facatativa','2026-02-07 07:30:00','2026-02-07 08:00:00',
 20000,'completada','domicilio','Camara reemplazada. Llanta inspeccionada sin daños adicionales.',1),

(8, 19,10,5,9,'Llanta delantera rajada, la banda de rodamiento esta muy desgastada.',
 'Transmision Madrid','2026-02-12 10:00:00','2026-02-12 10:40:00',
 42000,'completada','taller','Llanta delantera reemplazada por Schwalbe Marathon. Excelente agarre.',0),

(9, 20,4,1,10,'Mantenimiento general, cadena y frenos necesitan atencion.',
 'Rueda y Pedal Madrid','2026-02-18 15:00:00','2026-02-18 15:55:00',
 29000,'completada','taller','Cadena lubricada, frenos calibrados, manubrio ajustado. Lista para rodar.',0),

(10,12,3,9,2,'Rueda trasera muy chueca, tiembla mucho al frenar a alta velocidad.',
 'CicloVia Facatativa','2026-02-22 11:00:00','2026-02-22 11:50:00',
 30000,'completada','taller','Centrado de rueda trasera realizado. Tension de rayos corregida. Sin vibraciones.',0),

-- ── MARZO 2026 ───────────────────────────────────────────────────
(11,13,5,11,3,'La cadena hace ruido al pedalear fuerte, necesita desengrase.',
 'Cll 5 Madrid','2026-03-04 09:30:00','2026-03-04 09:55:00',
 15000,'completada','taller','Cadena desengrasada, limpieza de platos y pinones. Lubricacion aplicada.',0),

(12,14,6,8,4,'Cable de freno trasero roto, no puedo frenar bien con la mano derecha.',
 'Taller del Ciclista Mosquera','2026-03-08 13:00:00','2026-03-08 13:35:00',
 25000,'completada','taller','Cable y funda de freno trasero reemplazados. Sistema ajustado correctamente.',0),

(13,15,8,6,5,'Frenos chirrian mucho y no agarran bien en lluvia.',
 'Bici Center Facatativa','2026-03-13 10:00:00','2026-03-13 10:40:00',
 23000,'completada','taller','Pastillas desgastadas reemplazadas, discos limpiados. Frenos silenciosos y efectivos.',0),

(14,16,10,14,6,'Se me fue la cadena y el derailer quedo torcido. Varado en la via.',
 'Via Madrid-Mosquera Km 5','2026-03-17 12:00:00','2026-03-17 12:45:00',
 50000,'completada','domicilio','Derailer enderezado, cadena reubicada y ajustada. Servicio prestado en via.',1),

(15,17,4,2,7,'Mantenimiento preventivo completo antes de temporada de lluvias.',
 'Rueda y Pedal Madrid','2026-03-21 09:00:00','2026-03-21 10:30:00',
 67000,'completada','taller','Desmontaje, limpieza y lubricacion total. Llantas y frenos revisados. Optima condicion.',0),

-- ── ABRIL 2026 ───────────────────────────────────────────────────
(16,18,2,1,8,'Mantenimiento mensual de rutina.',
 'CicloVia Facatativa','2026-04-05 10:00:00','2026-04-05 10:50:00',
 35000,'completada','taller','Mantenimiento completo realizado. Cadena, frenos y neumaticos en buenas condiciones.',0),

(17,19,6,3,9,'Pinchazo doble: llanta delantera y trasera.',
 'Taller del Ciclista Mosquera','2026-04-09 08:00:00','2026-04-09 08:45:00',
 24000,'completada','taller','Dos parches vulcanizados aplicados correctamente. Presion de llantas verificada.',0),

(18,20,10,7,10,'Cambios duros y ruidosos, especialmente en las marchas altas.',
 'Transmision Madrid','2026-04-14 14:30:00','2026-04-14 15:15:00',
 33000,'completada','taller','Transmision completa ajustada, cables tensados, limites calibrados. Cambios suaves.',0),

(19,12,8,15,1,'Instalar luces LED delanteras y traseras, y guardabarros.',
 'Bici Center Facatativa','2026-04-18 11:00:00','2026-04-18 11:40:00',
 27000,'completada','taller','Luces USB instaladas y guardabarros ajustados. Bicicleta lista para uso nocturno.',0),

(20,13,5,4,3,'Camara delantera con escape lento de aire.',
 'Cll 5 Madrid','2026-04-23 09:00:00','2026-04-23 09:30:00',
 18000,'completada','taller','Camara delantera reemplazada. Valvula verificada sin fugas.',0),

-- ── MAYO 2026 — MES ACTUAL ────────────────────────────────────────
(21,14,6,10,4,'Revision completa antes de viaje largo a Bogota.',
 'Taller del Ciclista Mosquera','2026-05-02 10:00:00','2026-05-02 11:30:00',
 40000,'completada','taller','Revision tecnica exitosa. Todo en optimas condiciones para el viaje.',0),

(22,15,8,2,5,'Mantenimiento profundo post-temporada de lluvias.',
 'Bici Center Facatativa','2026-05-05 09:00:00','2026-05-05 10:30:00',
 75000,'completada','taller','Limpieza profunda post-lluvia. Oxido en rayos removido. Transmision recalibrada.',0),

-- ORDENES ACTIVAS (no completadas)
(23,16,4,1,6,'Mantenimiento preventivo mensual programado.',
 'Rueda y Pedal Madrid','2026-05-06 08:00:00','2026-05-07 10:00:00',
 32000,'asignada','taller',NULL,0),

(24,17,NULL,14,7,'Cadena salida y derailer doblado. Varado en la entrada a Madrid.',
 'Entrada Madrid Via Bogota','2026-05-06 10:30:00','2026-05-06 11:30:00',
 52000,'pendiente','domicilio',NULL,1),

(25,18,NULL,6,8,'Frenos traseros no responden bien, peligroso en bajadas.',
 'Cra 3 No. 8-25, Facatativa','2026-05-06 11:00:00','2026-05-08 09:00:00',
 22000,'pendiente','taller',NULL,0);

-- ═══════════════════════════════════════════════════════════════════
-- DATOS: CALIFICACIONES (todas las ordenes completadas)
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO calificaciones (orden_id,mecanico_id,cliente_id,puntuacion,comentario,fecha) VALUES
(1, 2,12,5,'Carlos excelente, llego puntual y dejo la bici como nueva. Super recomendado.','2026-01-08 11:00:00'),
(2, 4,13,5,'Andres muy profesional. El freno quedo perfecto, sin ruidos ni problemas.','2026-01-12 13:00:00'),
(3, 6,14,4,'Sergio llego rapido a la emergencia. Resolvio bien aunque tardo un poco mas de lo dicho.','2026-01-15 10:00:00'),
(4, 8,15,5,'Luis hizo una revision muy completa con informe detallado. Excelente atencion.','2026-01-20 12:00:00'),
(5, 6,16,5,'Sergio experto en cambios. Todo calibrado perfectamente, la bici cambia sola.','2026-01-25 16:00:00'),
(6, 7,17,5,'Laura es un crack, dejo la bici como el primer dia. Vale cada peso.','2026-02-03 12:00:00'),
(7, 2,18,4,'Carlos llego rapido a domicilio. Buen trabajo con la camara aunque el precio me parecio justo.','2026-02-07 09:00:00'),
(8,10,19,4,'Hector hizo buen trabajo con la llanta. Solo tardo un poco mas de lo esperado.','2026-02-12 12:00:00'),
(9, 4,20,5,'Andres muy eficiente y amable. La bici quedo perfecta con el mantenimiento.','2026-02-18 17:00:00'),
(10,3,12,5,'Diana experta en centrado de ruedas. Sin vibraciones, la bici rueda suavemente.','2026-02-22 13:00:00'),
(11,5,13,4,'Felipe rapido y eficiente con la limpieza de cadena. Precio justo.','2026-03-04 11:00:00'),
(12,6,14,5,'Sergio muy habil con los cables. El freno quedo perfecto, sin juego.','2026-03-08 15:00:00'),
(13,8,15,5,'Camila hizo un trabajo impecable con los frenos. Silenciosos y potentes.','2026-03-13 11:30:00'),
(14,10,16,3,'Hector llego rapido pero cobro mas de lo acordado. El trabajo estuvo bien.','2026-03-17 14:00:00'),
(15,4,17,5,'Andres muy profesional en el mantenimiento completo. Vale cada peso invertido.','2026-03-21 11:00:00'),
(16,2,18,5,'Carlos siempre constante y puntual. Excelente mantenimiento mensual.','2026-04-05 12:00:00'),
(17,6,19,5,'Sergio resolvio los dos pinchazos rapido y bien. Muy recomendado.','2026-04-09 10:00:00'),
(18,10,20,4,'Hector buen trabajo con la transmision. Los cambios quedaron mucho mejores.','2026-04-14 16:00:00'),
(19,8,12,5,'Luis instalo todo perfecto. Las luces son excelentes para la noche.','2026-04-18 12:30:00'),
(20,5,13,5,'Felipe rapido y preciso. Camara nueva sin fugas, precio muy justo.','2026-04-23 10:30:00'),
(21,6,14,5,'Sergio revision tecnica muy completa, me fue al viaje con total tranquilidad.','2026-05-02 12:30:00'),
(22,8,15,5,'Luis trabajo impecable post-lluvia, todo limpio y ajustado. Muy satisfecha.','2026-05-05 11:30:00');

-- ═══════════════════════════════════════════════════════════════════
-- ACTUALIZAR ESTADISTICAS MECANICOS
-- ═══════════════════════════════════════════════════════════════════
UPDATE mecanicos m SET
    total_servicios = (
        SELECT COUNT(*) FROM ordenes
        WHERE mecanico_id = m.usuario_id AND estado = 'completada'
    ),
    calificacion_promedio = (
        SELECT COALESCE(ROUND(AVG(puntuacion), 2), 0.00)
        FROM calificaciones WHERE mecanico_id = m.usuario_id
    );

-- Actualizar calificacion de talleres basada en sus mecanicos
UPDATE talleres t SET
    calificacion = (
        SELECT COALESCE(ROUND(AVG(m.calificacion_promedio), 2), 0.00)
        FROM taller_mecanicos tm
        JOIN mecanicos m ON m.usuario_id = tm.mecanico_id
        WHERE tm.taller_id = t.id
    ),
    total_resenas = (
        SELECT COUNT(*)
        FROM taller_mecanicos tm
        JOIN mecanicos m ON m.usuario_id = tm.mecanico_id
        JOIN calificaciones c ON c.mecanico_id = m.usuario_id
        WHERE tm.taller_id = t.id
    );

-- ═══════════════════════════════════════════════════════════════════
-- NOTIFICACIONES
-- ═══════════════════════════════════════════════════════════════════
INSERT INTO notificaciones (usuario_id,tipo,titulo,mensaje,leida) VALUES
(12,'orden','Servicio completado','Tu mantenimiento fue completado exitosamente. Califica al mecanico.',1),
(16,'orden','Orden asignada','Tu orden #23 fue asignada a Andres Torres. Te contactara pronto.',0),
(17,'urgente','Orden de emergencia recibida','Recibimos tu solicitud urgente #24. Asignando mecanico disponible.',0),
(18,'orden','Orden recibida','Tu solicitud de ajuste de frenos #25 fue recibida. La agendaremos pronto.',0),
(2,'sistema','Nueva orden asignada','Se te asigno la orden #23 de Santiago Vargas.',0),
(6,'sistema','Felicitaciones','Tu calificacion promedio subio a 4.90. Eres el mecanico mejor valorado.',1);

-- ═══════════════════════════════════════════════════════════════════
-- VERIFICACION FINAL
-- ═══════════════════════════════════════════════════════════════════
SELECT 'Base de datos BiciFix v5 instalada correctamente' AS resultado;

SELECT
    (SELECT COUNT(*) FROM usuarios WHERE rol='cliente')    AS clientes,
    (SELECT COUNT(*) FROM usuarios WHERE rol='mecanico')   AS mecanicos,
    (SELECT COUNT(*) FROM talleres)                         AS talleres,
    (SELECT COUNT(*) FROM ordenes)                          AS total_ordenes,
    (SELECT COUNT(*) FROM ordenes WHERE estado='completada') AS completadas,
    (SELECT COUNT(*) FROM ordenes WHERE estado='pendiente')  AS pendientes,
    (SELECT COUNT(*) FROM calificaciones)                    AS calificaciones,
    (SELECT CONCAT('$', FORMAT(SUM(precio_final),0)) FROM ordenes WHERE estado='completada') AS ingresos_total;

SELECT CONCAT(u.nombre,' ',u.apellido) AS mecanico,
       m.total_servicios, m.calificacion_promedio,
       t.nombre AS taller
FROM mecanicos m
JOIN usuarios u ON u.id = m.usuario_id
JOIN taller_mecanicos tm ON tm.mecanico_id = u.id
JOIN talleres t ON t.id = tm.taller_id
ORDER BY m.calificacion_promedio DESC;
