from flask import Flask, render_template, request, session, redirect, url_for, flash
from config import Config
import pymysql, pymysql.cursors
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Zona horaria Colombia (UTC-5, sin horario de verano)
TZ_COL = timezone(timedelta(hours=-5))
def now_col():
    return datetime.now(TZ_COL).replace(tzinfo=None)

app = Flask(__name__)
app.config.from_object(Config)

# ─── FILTROS ─────────────────────────────────────────────────
@app.template_filter("fecha")
def formato_fecha(value, fmt="%d/%m/%Y"):
    if value is None: return ""
    if hasattr(value, "strftime"): return value.strftime(fmt)
    return str(value)[:10]

@app.template_filter("cop")
def formato_cop(value):
    """Formatea un numero como precio COP: 115000 → $115.000"""
    try:
        n = int(float(value))
        return "${:,.0f}".format(n).replace(",", ".")
    except (ValueError, TypeError):
        return "$0"

# ─── DB ──────────────────────────────────────────────────────
def get_db():
    return pymysql.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"],
        port=app.config["MYSQL_PORT"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        ssl={"ssl": {}}
    )

def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nombre VARCHAR(80) NOT NULL, apellido VARCHAR(80) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL, password VARCHAR(255) NOT NULL,
        telefono VARCHAR(20), ciudad VARCHAR(80),
        rol ENUM('admin','mecanico','cliente') DEFAULT 'cliente',
        activo TINYINT(1) DEFAULT 1,
        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS mecanicos (
        id INT PRIMARY KEY AUTO_INCREMENT,
        usuario_id INT NOT NULL, zona VARCHAR(100),
        certificaciones TEXT,
        calificacion_promedio DECIMAL(3,2) DEFAULT 0.00,
        total_servicios INT DEFAULT 0,
        estado_mecanico ENUM('disponible','ocupado','inactivo') DEFAULT 'disponible',
        fecha_ingreso DATE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bicicletas (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INT NOT NULL, marca VARCHAR(80), modelo VARCHAR(80),
        color VARCHAR(40), tipo VARCHAR(40), anio INT, descripcion TEXT,
        FOREIGN KEY (cliente_id) REFERENCES usuarios(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS servicios (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nombre VARCHAR(120) NOT NULL, descripcion TEXT, icono VARCHAR(10) DEFAULT '',
        categoria VARCHAR(60) DEFAULT 'General',
        precio_min DECIMAL(10,2) DEFAULT 10.00, precio_max DECIMAL(10,2) DEFAULT 50.00,
        tiempo_estimado VARCHAR(40) DEFAULT '45 min', activo TINYINT(1) DEFAULT 1,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ordenes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        cliente_id INT NOT NULL, mecanico_id INT,
        servicio_id INT NOT NULL, bici_id INT,
        descripcion_problema TEXT, ubicacion VARCHAR(255),
        fecha_solicitud DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_servicio DATETIME, precio_final DECIMAL(10,2) DEFAULT 0,
        estado ENUM('pendiente','asignada','en_camino','proceso','completada','cancelada') DEFAULT 'pendiente',
        observaciones_mecanico TEXT, emergencia TINYINT(1) DEFAULT 0,
        tipo_atencion ENUM('taller','domicilio','recogida') DEFAULT 'taller',
        FOREIGN KEY (cliente_id) REFERENCES usuarios(id),
        FOREIGN KEY (servicio_id) REFERENCES servicios(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS calificaciones (
        id INT PRIMARY KEY AUTO_INCREMENT,
        orden_id INT NOT NULL UNIQUE, mecanico_id INT,
        cliente_id INT, puntuacion TINYINT, comentario TEXT,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (orden_id) REFERENCES ordenes(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    # Servicios iniciales — ON DUPLICATE KEY UPDATE fuerza actualización de precios a pesos COP
    cur.execute("""INSERT INTO servicios (id,nombre,descripcion,icono,precio_min,precio_max,tiempo_estimado) VALUES
        (1,'Mantenimiento preventivo basico','Limpieza, lubricacion de cadena, revision de frenos y cambios.','🔧',25000,40000,'45 min'),
        (2,'Parchado de llanta','Localizacion del pinchazo y reparacion de la camara de aire.','🔩',10000,18000,'20 min'),
        (3,'Cambio de camara de aire','Reemplazo completo de la camara de aire dañada.','🔄',15000,30000,'25 min'),
        (4,'Ajuste de frenos','Calibracion de frenos delanteros y traseros.','⚡',15000,30000,'30 min'),
        (5,'Ajuste de cambios y transmision','Calibracion de descarriladores, cables y palancas.','⚙️',20000,40000,'40 min'),
        (6,'Mantenimiento preventivo completo','Desmontaje, limpieza profunda, lubricacion total, ajuste integral.','🌟',55000,85000,'90 min'),
        (7,'Cambio de llanta completa','Reemplazo de la llanta externa por desgaste o daño.','🔄',25000,60000,'30 min'),
        (8,'Atencion de emergencia en via','Atencion inmediata donde fallo la bicicleta.','🚨',30000,60000,'45 min'),
        (9,'Revision tecnica completa','Diagnostico integral con informe detallado.','📋',30000,50000,'60 min'),
        (10,'Centrado de rueda','Correccion de tension de rayos para rueda recta.','🎯',20000,40000,'40 min')
    AS nuevos(id,nombre,descripcion,icono,precio_min,precio_max,tiempo_estimado)
    ON DUPLICATE KEY UPDATE
        precio_min=nuevos.precio_min,
        precio_max=nuevos.precio_max
    """)
    # Tablas modulo talleres
    cur.execute("""CREATE TABLE IF NOT EXISTS talleres (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nombre VARCHAR(120) NOT NULL, descripcion TEXT,
        direccion VARCHAR(255) NOT NULL, ciudad VARCHAR(80) NOT NULL DEFAULT 'Bogota',
        barrio VARCHAR(100), telefono VARCHAR(20), email VARCHAR(120),
        horario VARCHAR(120) DEFAULT 'Lun-Sab 8:00am-6:00pm',
        lat DECIMAL(10,7), lng DECIMAL(10,7),
        calificacion DECIMAL(3,2) NOT NULL DEFAULT 0.00,
        total_resenas INT NOT NULL DEFAULT 0,
        activo TINYINT(1) NOT NULL DEFAULT 1,
        fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS taller_mecanicos (
        taller_id INT NOT NULL, mecanico_id INT NOT NULL,
        PRIMARY KEY (taller_id, mecanico_id),
        FOREIGN KEY (taller_id)   REFERENCES talleres(id) ON DELETE CASCADE,
        FOREIGN KEY (mecanico_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS taller_servicios (
        taller_id INT NOT NULL, servicio_id INT NOT NULL,
        PRIMARY KEY (taller_id, servicio_id),
        FOREIGN KEY (taller_id)   REFERENCES talleres(id)  ON DELETE CASCADE,
        FOREIGN KEY (servicio_id) REFERENCES servicios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("SELECT COUNT(*) as c FROM talleres")
    if cur.fetchone()["c"] == 0:
        cur.execute("""INSERT INTO talleres
            (id,nombre,descripcion,direccion,ciudad,barrio,telefono,email,horario,lat,lng,calificacion,total_resenas,activo)
            VALUES
            (1,'Ciclo Center Chapinero',
             'Taller especializado en MTB y bicicletas de ruta con herramientas profesionales y repuestos originales.',
             'Cra 7 # 52-15','Bogota','Chapinero','601-555-0101','chapinero@ciclocenter.com',
             'Lun-Sab 8:00am-7:00pm',4.6441700,-74.0631200,4.80,42,1),
            (2,'Rueda Libre Kennedy',
             'Especialistas en bicicletas electricas y sistemas Shimano. Precios justos para el sur de Bogota.',
             'Cll 38 Sur # 82-20','Bogota','Kennedy','601-555-0202','info@ruedalibrekennedy.com',
             'Lun-Sab 8:00am-6:00pm',4.6288900,-74.1491800,4.60,28,1),
            (3,'Pedal Norte Usaquen',
             'Taller moderno en el norte de Bogota con equipos de diagnostico digital y servicio expres.',
             'Cll 119 # 6-40','Bogota','Usaquen','601-555-0303','contacto@pedalnorte.com',
             'Lun-Dom 7:00am-8:00pm',4.6954200,-74.0304400,4.90,61,1),
            (4,'Bici Taller El Poblado',
             'Servicio premium en Medellin. Mecanicos certificados por SENA, especialistas en MTB de alta gama.',
             'Cll 10 # 35-28','Medellin','El Poblado','604-555-0404','info@bicitallerpoblado.com',
             'Lun-Sab 9:00am-6:00pm',6.2084200,-75.5684000,4.90,55,1),
            (5,'Transmision Laureles',
             'Taller en Medellin zona oeste, bicicletas urbanas y commuters, venta de accesorios y repuestos.',
             'Cra 76 # 33-12','Medellin','Laureles','604-555-0505','ventas@transmisionlaureles.com',
             'Lun-Sab 8:00am-6:00pm',6.2451100,-75.5971200,4.50,19,1)""")
        cur.execute("""INSERT IGNORE INTO taller_mecanicos (taller_id, mecanico_id)
            VALUES (1,2),(2,3),(3,2),(4,4),(5,4)""")
        cur.execute("""INSERT IGNORE INTO taller_servicios (taller_id, servicio_id)
            SELECT t.id, s.id FROM talleres t, servicios s WHERE s.activo=1""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pausas_mecanico (
        id            INT      PRIMARY KEY AUTO_INCREMENT,
        mecanico_id   INT      NOT NULL,
        motivo        VARCHAR(120) NOT NULL DEFAULT 'Pausa',
        inicio        DATETIME NOT NULL,
        fin           DATETIME NOT NULL,
        activa        TINYINT(1) NOT NULL DEFAULT 1,
        FOREIGN KEY (mecanico_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS notificaciones (
        id           INT          PRIMARY KEY AUTO_INCREMENT,
        usuario_id   INT          NOT NULL,
        tipo         ENUM('mantenimiento','manual','orden','sistema') NOT NULL DEFAULT 'manual',
        titulo       VARCHAR(120) NOT NULL,
        mensaje      TEXT         NOT NULL,
        leida        TINYINT(1)   NOT NULL DEFAULT 0,
        fecha        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    # Admin por defecto
    cur.execute("SELECT id FROM usuarios WHERE email='admin@bicifix.com'")
    if not cur.fetchone():
        cur.execute("INSERT INTO usuarios (nombre,apellido,email,password,rol,ciudad) VALUES (%s,%s,%s,%s,%s,%s)",
            ('Admin','BiciFix','admin@bicifix.com',generate_password_hash('admin123'),'admin','Bogota'))
    conn.commit(); cur.close(); conn.close()
    print("[DB] BiciFix DB inicializada correctamente")

    # Migraciones: columnas agregadas en versiones anteriores
    migraciones = [
        "ALTER TABLE ordenes ADD COLUMN tipo_atencion ENUM('taller','domicilio','recogida') DEFAULT 'taller'",
        "ALTER TABLE servicios ADD COLUMN categoria VARCHAR(60) DEFAULT 'General'",
        "ALTER TABLE mecanicos ADD COLUMN certificaciones TEXT",
        "ALTER TABLE mecanicos ADD COLUMN fecha_ingreso DATE",
    ]
    try:
        conn2 = get_db(); cur2 = conn2.cursor()
        for sql in migraciones:
            try:
                cur2.execute(sql)
            except Exception:
                pass  # Columna ya existe
        conn2.commit(); cur2.close(); conn2.close()
    except Exception:
        pass

try:
    init_db()
except Exception as e:
    print(f"[DB ERROR] {e}")

# ─── DECORADORES ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "usuario" not in session:
            flash("Debes iniciar sesion primero","error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "usuario" not in session or session["usuario"]["rol"] != "admin":
            flash("Acceso restringido","error"); return redirect(url_for("index"))
        return f(*a, **kw)
    return dec

def mecanico_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "usuario" not in session or session["usuario"]["rol"] != "mecanico":
            flash("Acceso restringido","error"); return redirect(url_for("index"))
        return f(*a, **kw)
    return dec

def cliente_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "usuario" not in session or session["usuario"]["rol"] != "cliente":
            flash("Acceso restringido","error"); return redirect(url_for("index"))
        return f(*a, **kw)
    return dec

# ─── RUTAS PÚBLICAS ──────────────────────────────────────────
@app.route("/")
def index():
    if "usuario" in session:
        r = session["usuario"]["rol"]
        if r == "admin": return redirect("/admin")
        if r == "mecanico": return redirect("/mecanico")
        return redirect("/dashboard")
    return render_template("bienvenida.html")

@app.route("/servicios")
def servicios():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM servicios WHERE activo=1 ORDER BY id")
    svcs = cur.fetchall(); cur.close(); conn.close()
    return render_template("servicios.html", servicios=svcs)

@app.route("/api/usuarios-acceso")
def api_usuarios_acceso():
    from flask import jsonify
    # Contraseñas por defecto según rol (solo para acceso rápido en desarrollo)
    DEFAULT_PW = {"admin": "admin123", "mecanico": "mecanico123", "cliente": "cliente123"}
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT nombre, apellido, email, rol FROM usuarios WHERE activo=1 ORDER BY FIELD(rol,'admin','mecanico','cliente'), nombre")
    rows = cur.fetchall(); cur.close(); conn.close()
    return jsonify([{"nombre": r["nombre"], "apellido": r["apellido"],
                     "email": r["email"], "rol": r["rol"],
                     "pw": DEFAULT_PW.get(r["rol"], "123456")} for r in rows])

@app.route("/login", methods=["GET","POST"])
def login():
    if "usuario" in session: return redirect("/")
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw    = request.form.get("password","")
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email=%s AND activo=1", (email,))
        u = cur.fetchone(); cur.close(); conn.close()
        if u and check_password_hash(u["password"], pw):
            session["usuario"] = {"id":u["id"],"nombre":u["nombre"],"email":u["email"],"rol":u["rol"]}
            flash(f"Bienvenido, {u['nombre']}!","success")
            if u["rol"]=="admin": return redirect("/admin")
            if u["rol"]=="mecanico": return redirect("/mecanico")
            return redirect("/dashboard")
        flash("Correo o contraseña incorrectos","error")
    return render_template("login.html")

@app.route("/registro", methods=["GET","POST"])
def registro():
    if "usuario" in session: return redirect("/")
    if request.method == "POST":
        n  = request.form.get("nombre","").strip()
        ap = request.form.get("apellido","").strip()
        em = request.form.get("email","").strip()
        pw = request.form.get("password","")
        cf = request.form.get("confirmar","")
        tf = request.form.get("telefono","").strip()
        ci = request.form.get("ciudad","").strip()
        if not all([n,ap,em,pw,cf]):
            flash("Completa todos los campos","error"); return render_template("registro.html")
        if len(pw) < 6:
            flash("La contrasena debe tener minimo 6 caracteres","error"); return render_template("registro.html")
        if pw != cf:
            flash("Las contrasenas no coinciden","error"); return render_template("registro.html")
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (em,))
        if cur.fetchone():
            flash("Este correo ya esta registrado","error"); cur.close(); conn.close()
            return render_template("registro.html")
        cur.execute("INSERT INTO usuarios (nombre,apellido,email,password,telefono,ciudad,rol) VALUES (%s,%s,%s,%s,%s,%s,'cliente')",
            (n,ap,em,generate_password_hash(pw),tf,ci))
        conn.commit()
        cur.execute("SELECT * FROM usuarios WHERE email=%s", (em,))
        u = cur.fetchone(); cur.close(); conn.close()
        session["usuario"] = {"id":u["id"],"nombre":u["nombre"],"email":u["email"],"rol":"cliente"}
        flash(f"Cuenta creada exitosamente. Bienvenido a BiciFix, {n}!","success")
        return redirect("/dashboard")
    return render_template("registro.html")

@app.route("/recuperar", methods=["GET","POST"])
def recuperar():
    if request.method == "POST":
        em = request.form.get("email","").strip()
        nu = request.form.get("nueva","")
        cf = request.form.get("confirmar","")
        if len(nu) < 6:
            flash("La contrasena debe tener minimo 6 caracteres","error")
            return render_template("recuperar.html")
        if nu != cf:
            flash("Las contrasenas no coinciden","error")
            return render_template("recuperar.html")
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (em,))
        u = cur.fetchone()
        if not u:
            flash("Correo no encontrado en el sistema","error"); cur.close(); conn.close()
            return render_template("recuperar.html")
        cur.execute("UPDATE usuarios SET password=%s WHERE email=%s", (generate_password_hash(nu), em))
        conn.commit(); cur.close(); conn.close()
        flash("Contrasena actualizada correctamente. Ya puedes ingresar.","success")
        return redirect("/login")
    return render_template("recuperar.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

# ─── CLIENTE ─────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    if session["usuario"]["rol"] != "cliente": return redirect("/")
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE cliente_id=%s", (uid,))
    tot = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE cliente_id=%s AND estado IN ('pendiente','asignada','en_camino','proceso')", (uid,))
    pend = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE cliente_id=%s AND estado='completada'", (uid,))
    comp = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM bicicletas WHERE cliente_id=%s", (uid,))
    bicis = cur.fetchone()["c"]
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id
        WHERE o.cliente_id=%s ORDER BY o.fecha_solicitud DESC LIMIT 5""", (uid,))
    ultimas = cur.fetchall()
    cur.execute("SELECT * FROM bicicletas WHERE cliente_id=%s LIMIT 4", (uid,))
    bicicletas = cur.fetchall()
    cur.close(); conn.close()
    stats = {"total_ordenes":tot,"pendientes":pend,"completadas":comp,"bicicletas":bicis}
    return render_template("dashboard.html", stats=stats, ultimas_ordenes=ultimas, bicicletas=bicicletas)

@app.route("/solicitar", methods=["GET","POST"])
@login_required
def solicitar():
    if session["usuario"]["rol"] != "cliente": return redirect("/")
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    if request.method == "POST":
        from datetime import datetime, date, time as dtime
        sv         = request.form.get("servicio_id")
        bi         = request.form.get("bici_id")
        desc       = request.form.get("descripcion","").strip()
        ubi        = request.form.get("ubicacion","").strip()
        fec        = request.form.get("fecha","")
        hor        = request.form.get("hora","")
        emg        = int(request.form.get("emergencia","0"))
        mec_id     = request.form.get("mecanico_id") or None
        tipo_aten  = request.form.get("tipo_atencion","taller")  # taller | domicilio | recogida
        error = False

        # Costo adicional segun tipo de atencion
        costo_adicional = {"domicilio": 8000, "recogida": 12000}.get(tipo_aten, 0)

        if not all([sv, bi, desc, fec, hor]):
            flash("Completa todos los campos obligatorios.", "error")
            error = True
        if not ubi and tipo_aten in ("domicilio","recogida"):
            flash("Debes ingresar la direccion para el servicio a domicilio o recogida.", "error")
            error = True

        if not error:
            # ── Validación fecha/hora en servidor ──
            try:
                fecha_obj = datetime.strptime(f"{fec} {hor}", "%Y-%m-%d %H:%M")
                ahora     = now_col()
                hoy_col   = ahora.date()
                if fecha_obj.date() < hoy_col:
                    flash("La fecha no puede ser anterior a hoy.", "error")
                    error = True
                elif fecha_obj.date() == hoy_col and fecha_obj.time() < ahora.time().replace(second=0, microsecond=0):
                    flash("La hora no puede ser anterior a la hora actual.", "error")
                    error = True
            except ValueError:
                flash("Fecha u hora con formato inválido.", "error")
                error = True

        # ── Validación: mecanico sin cita duplicada (con solapamiento por duración) ──
        if not error and mec_id and fec and hor:
            cur.execute("""
                SELECT o.id FROM ordenes o
                JOIN servicios s ON s.id = o.servicio_id
                WHERE o.mecanico_id = %s
                  AND DATE(o.fecha_servicio) = %s
                  AND o.estado NOT IN ('cancelada','completada')
                  AND (
                    o.fecha_servicio < DATE_ADD(STR_TO_DATE(%s, '%%Y-%%m-%%d %%H:%%i'),
                                                INTERVAL CAST(REGEXP_REPLACE(s.tiempo_estimado,'[^0-9].*','') AS UNSIGNED) MINUTE)
                    AND DATE_ADD(o.fecha_servicio,
                                 INTERVAL CAST(REGEXP_REPLACE(s.tiempo_estimado,'[^0-9].*','') AS UNSIGNED) MINUTE)
                        > STR_TO_DATE(%s, '%%Y-%%m-%%d %%H:%%i')
                  )
                LIMIT 1
            """, (mec_id, fec, f"{fec} {hor}", f"{fec} {hor}"))
            if cur.fetchone():
                flash("Ese mecánico ya tiene una cita que se solapa con ese horario. Por favor elige otra hora.", "error")
                error = True

        # ── Validación: el cliente no puede tener otra cita a la misma hora ──
        if not error and fec and hor:
            cur.execute("""
                SELECT o.id FROM ordenes o
                JOIN servicios s ON s.id = o.servicio_id
                WHERE o.cliente_id = %s
                  AND DATE(o.fecha_servicio) = %s
                  AND o.estado NOT IN ('cancelada','completada')
                  AND (
                    o.fecha_servicio < DATE_ADD(STR_TO_DATE(%s, '%%Y-%%m-%%d %%H:%%i'),
                                                INTERVAL CAST(REGEXP_REPLACE(s.tiempo_estimado,'[^0-9].*','') AS UNSIGNED) MINUTE)
                    AND DATE_ADD(o.fecha_servicio,
                                 INTERVAL CAST(REGEXP_REPLACE(s.tiempo_estimado,'[^0-9].*','') AS UNSIGNED) MINUTE)
                        > STR_TO_DATE(%s, '%%Y-%%m-%%d %%H:%%i')
                  )
                LIMIT 1
            """, (uid, fec, f"{fec} {hor}", f"{fec} {hor}"))
            if cur.fetchone():
                flash("Ya tienes una cita agendada que se solapa con ese horario. No puedes agendar dos servicios al mismo tiempo.", "error")
                error = True

        # ── Validación: la bicicleta no puede tener una orden activa pendiente ──
        if not error and bi:
            cur.execute("""
                SELECT o.id, DATE_FORMAT(o.fecha_servicio,'%%d/%%m/%%Y %%H:%%i') as fec_fmt
                FROM ordenes o
                WHERE o.bici_id = %s
                  AND o.cliente_id = %s
                  AND o.estado NOT IN ('cancelada','completada')
                LIMIT 1
            """, (bi, uid))
            ord_activa = cur.fetchone()
            if ord_activa:
                flash(f"Esa bicicleta ya tiene una orden activa (agendada para {ord_activa['fec_fmt']}). Cancélala o espera a que se complete antes de agendar otra.", "error")
                error = True

        if not error:
            cur.execute("SELECT precio_min,precio_max FROM servicios WHERE id=%s", (sv,))
            svc = cur.fetchone()
            precio = ((svc["precio_min"] + svc["precio_max"]) / 2 + costo_adicional) if svc else costo_adicional
            fecha_svc = f"{fec} {hor}"
            cur.execute("""INSERT INTO ordenes
                (cliente_id,servicio_id,bici_id,descripcion_problema,ubicacion,
                 fecha_servicio,precio_final,emergencia,mecanico_id,tipo_atencion)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uid, sv, bi, desc, ubi, fecha_svc, precio, emg, mec_id, tipo_aten))
            # Si el cliente escogió mecánico, marcar la orden como asignada
            if mec_id:
                orden_id = cur.lastrowid
                cur.execute("UPDATE ordenes SET estado='asignada' WHERE id=%s", (orden_id,))
            conn.commit()
            msg = "Servicio solicitado exitosamente."
            if mec_id:
                msg += " El mecánico seleccionado ha sido asignado."
            else:
                msg += " Pronto asignaremos un mecánico."
            flash(msg, "success")
            cur.close(); conn.close()
            return redirect("/mis-ordenes")

    cur.execute("SELECT * FROM servicios WHERE activo=1 ORDER BY nombre")
    svcs = cur.fetchall()
    cur.execute("SELECT * FROM bicicletas WHERE cliente_id=%s", (uid,))
    bicis = cur.fetchall()
    cur.execute("SELECT * FROM talleres WHERE activo=1 ORDER BY ciudad, nombre")
    talleres_list = cur.fetchall()
    cur.close(); conn.close()
    return render_template("cliente/solicitar.html", servicios=svcs, bicicletas=bicis, talleres=talleres_list)

@app.route("/api/citas-cliente")
@login_required
def api_citas_cliente():
    """Devuelve citas activas del cliente para validación en el frontend."""
    import re as _re
    from flask import jsonify
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT DATE_FORMAT(o.fecha_servicio,'%%Y-%%m-%%d') as fecha,
               TIME_FORMAT(o.fecha_servicio,'%%H:%%i') as hora,
               s.nombre as servicio,
               s.tiempo_estimado,
               b.marca, b.modelo, b.color,
               o.bici_id, o.id as orden_id
        FROM ordenes o
        JOIN servicios s ON s.id = o.servicio_id
        LEFT JOIN bicicletas b ON b.id = o.bici_id
        WHERE o.cliente_id = %s
          AND o.fecha_servicio >= NOW()
          AND o.estado NOT IN ('cancelada','completada')
        ORDER BY o.fecha_servicio ASC
    """, (uid,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    def parse_mins(t):
        if not t: return 60
        nums = [int(x) for x in _re.findall(r'\d+', str(t))]
        if not nums: return 60
        m = max(nums)
        return m * 60 if (m <= 6 and len(nums) == 1) else m

    result = []
    for r in rows:
        mins = parse_mins(r["tiempo_estimado"])
        mins = ((mins + 29) // 30) * 30
        result.append({
            "fecha":        r["fecha"],
            "hora":         r["hora"],
            "servicio":     r["servicio"],
            "duracion_mins": mins,
            "bici_id":      r["bici_id"],
            "bici_label":   f"{r['marca']} {r['modelo']} ({r['color']})" if r["marca"] else "",
            "orden_id":     r["orden_id"]
        })
    return jsonify(result)

@app.route("/api/mecanicos-taller/<int:taller_id>")
@login_required
def api_mecanicos_taller(taller_id):
    from flask import jsonify
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.nombre, u.apellido,
               m.calificacion_promedio, m.total_servicios, m.estado_mecanico, m.zona
        FROM taller_mecanicos tm
        JOIN usuarios  u ON u.id = tm.mecanico_id
        JOIN mecanicos m ON m.usuario_id = u.id
        WHERE tm.taller_id = %s AND u.activo = 1
        ORDER BY m.estado_mecanico ASC, m.calificacion_promedio DESC
    """, (taller_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    result = []
    for r in rows:
        result.append({
            "id":           r["id"],
            "nombre":       r["nombre"],
            "apellido":     r["apellido"],
            "calificacion": float(r["calificacion_promedio"]),
            "servicios":    r["total_servicios"],
            "estado":       r["estado_mecanico"],
            "zona":         r["zona"] or ""
        })
    return jsonify(result)



@app.route("/api/agenda-mecanico/<int:mec_id>")
@login_required
def api_agenda_mecanico(mec_id):
    """Devuelve las citas ocupadas del mecanico en el mes actual y siguiente."""
    from flask import jsonify
    from datetime import date, timedelta
    conn = get_db(); cur = conn.cursor()
    # Obtener ordenes activas del mecanico en los próximos 60 dias
    cur.execute("""
        SELECT DATE_FORMAT(fecha_servicio,'%%Y-%%m-%%d') as fecha,
               TIME_FORMAT(fecha_servicio,'%%H:%%i') as hora,
               estado, s.nombre as servicio
        FROM ordenes o
        JOIN servicios s ON s.id = o.servicio_id
        WHERE o.mecanico_id = %s
          AND o.fecha_servicio >= NOW()
          AND o.fecha_servicio <= DATE_ADD(NOW(), INTERVAL 60 DAY)
          AND o.estado NOT IN ('cancelada','completada')
        ORDER BY fecha_servicio ASC
    """, (mec_id,))
    citas = cur.fetchall()
    # Dias de descanso (domingos) y estado general
    cur.execute("SELECT estado_mecanico FROM mecanicos WHERE usuario_id=%s", (mec_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    estado_general = row["estado_mecanico"] if row else "disponible"
    ocupados = []
    for c in citas:
        ocupados.append({
            "fecha":   c["fecha"],
            "hora":    c["hora"],
            "servicio": c["servicio"],
            "estado":  c["estado"]
        })
    return jsonify({"estado": estado_general, "citas": ocupados})

@app.route("/api/citas-mecanico/<int:mec_id>")
@login_required
def api_citas_mecanico(mec_id):
    """Devuelve citas ocupadas del mecanico como array plano para el calendario del cliente."""
    import re as _re
    from flask import jsonify
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT DATE_FORMAT(o.fecha_servicio,'%%Y-%%m-%%d') as fecha,
               TIME_FORMAT(o.fecha_servicio,'%%H:%%i') as hora,
               s.nombre as servicio, s.tiempo_estimado, o.estado
        FROM ordenes o
        JOIN servicios s ON s.id = o.servicio_id
        WHERE o.mecanico_id = %s
          AND o.fecha_servicio >= CURDATE()
          AND o.fecha_servicio <= DATE_ADD(CURDATE(), INTERVAL 90 DAY)
          AND o.estado NOT IN ('cancelada','completada')
        ORDER BY o.fecha_servicio ASC
    """, (mec_id,))
    citas = cur.fetchall()
    cur.close()

    def parse_mins(t):
        """Convierte '45 min', '1h 30min', '30-60 min' -> minutos (usa el maximo)."""
        if not t: return 60
        nums = [int(x) for x in _re.findall(r'\d+', str(t))]
        if not nums: return 60
        # Si el valor mayor es <=6, probablemente son horas: ej "2 h"
        m = max(nums)
        if m <= 6 and len(nums) == 1:
            return m * 60
        return m  # ya está en minutos

    result = []
    for c in citas:
        mins = parse_mins(c["tiempo_estimado"])
        # Redondear al multiplo de 30 superior
        mins = ((mins + 29) // 30) * 30
        result.append({
            "fecha":    c["fecha"],
            "hora":     c["hora"],
            "servicio": c["servicio"],
            "duracion_mins": mins
        })

    # Incluir pausas programadas como bloques ocupados
    cur2 = conn.cursor()
    cur2.execute("""
        SELECT DATE_FORMAT(inicio,'%%Y-%%m-%%d') as fecha,
               TIME_FORMAT(inicio,'%%H:%%i') as hora,
               motivo as servicio,
               TIMESTAMPDIFF(MINUTE, inicio, fin) as duracion_mins
        FROM pausas_mecanico
        WHERE mecanico_id = %s
          AND fin > NOW()
          AND inicio <= DATE_ADD(NOW(), INTERVAL 90 DAY)
    """, (mec_id,))
    for p in cur2.fetchall():
        mins_p = ((int(p["duracion_mins"]) + 29) // 30) * 30
        result.append({
            "fecha":         p["fecha"],
            "hora":          p["hora"],
            "servicio":      f"⏸ {p['servicio']}",
            "duracion_mins": mins_p,
            "es_pausa":      True
        })
    cur2.close()
    conn.close()
    return jsonify(result)

# ─── TALLERES ────────────────────────────────────────────────
@app.route("/talleres")
def talleres():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT t.*,
               COUNT(DISTINCT ts.servicio_id) AS total_servicios,
               COUNT(DISTINCT tm.mecanico_id) AS total_mecanicos
        FROM talleres t
        LEFT JOIN taller_servicios ts ON ts.taller_id = t.id
        LEFT JOIN taller_mecanicos tm ON tm.taller_id = t.id
        WHERE t.activo = 1
        GROUP BY t.id
        ORDER BY t.ciudad, t.calificacion DESC
    """)
    talleres = cur.fetchall()
    cur.close(); conn.close()
    return render_template("cliente/talleres.html", talleres=talleres)

@app.route("/talleres/<int:taller_id>")
def taller_detalle(taller_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM talleres WHERE id=%s AND activo=1", (taller_id,))
    taller = cur.fetchone()
    if not taller:
        cur.close(); conn.close()
        flash("Taller no encontrado.", "error")
        return redirect("/talleres")
    cur.execute("""
        SELECT u.id, u.nombre, u.apellido, u.telefono,
               m.zona, m.certificaciones,
               m.calificacion_promedio, m.total_servicios, m.estado_mecanico
        FROM taller_mecanicos tm
        JOIN usuarios  u ON u.id = tm.mecanico_id
        JOIN mecanicos m ON m.usuario_id = u.id
        WHERE tm.taller_id = %s AND u.activo = 1
        ORDER BY m.calificacion_promedio DESC
    """, (taller_id,))
    mecanicos = cur.fetchall()
    cur.execute("""
        SELECT s.*
        FROM taller_servicios ts
        JOIN servicios s ON s.id = ts.servicio_id
        WHERE ts.taller_id = %s AND s.activo = 1
        ORDER BY s.categoria, s.nombre
    """, (taller_id,))
    servicios = cur.fetchall()
    cur.close(); conn.close()
    return render_template("cliente/taller_detalle.html",
                           taller=taller, mecanicos=mecanicos, servicios=servicios)


@app.route("/mis-ordenes")
@login_required
def mis_ordenes():
    if session["usuario"]["rol"] != "cliente": return redirect("/")
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre,
        u.nombre as mecanico_nombre, c.puntuacion as calificacion
        FROM ordenes o JOIN servicios s ON o.servicio_id=s.id
        LEFT JOIN usuarios u ON o.mecanico_id=u.id
        LEFT JOIN calificaciones c ON c.orden_id=o.id
        WHERE o.cliente_id=%s ORDER BY o.fecha_solicitud DESC""", (uid,))
    ordenes = cur.fetchall(); cur.close(); conn.close()
    return render_template("cliente/mis_ordenes.html", ordenes=ordenes)

@app.route("/mis-bicicletas")
@login_required
def mis_bicicletas():
    if session["usuario"]["rol"] != "cliente": return redirect("/")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM bicicletas WHERE cliente_id=%s ORDER BY id DESC", (session["usuario"]["id"],))
    bicis = cur.fetchall(); cur.close(); conn.close()
    return render_template("cliente/mis_bicicletas.html", bicicletas=bicis)

@app.route("/mis-bicicletas/agregar", methods=["POST"])
@login_required
def agregar_bicicleta():
    if session["usuario"]["rol"] != "cliente": return redirect("/")
    uid = session["usuario"]["id"]
    marca = request.form.get("marca","").strip()
    modelo= request.form.get("modelo","").strip()
    color = request.form.get("color","").strip()
    tipo  = request.form.get("tipo","").strip()
    anio  = request.form.get("anio") or None
    desc  = request.form.get("descripcion","").strip()
    if not all([marca,modelo,color,tipo]):
        flash("Completa los campos obligatorios","error")
        return redirect("/mis-bicicletas")
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO bicicletas (cliente_id,marca,modelo,color,tipo,anio,descripcion) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (uid,marca,modelo,color,tipo,anio,desc))
    conn.commit(); cur.close(); conn.close()
    flash("Bicicleta agregada exitosamente","success")
    return redirect("/mis-bicicletas")

@app.route("/mis-bicicletas/<int:bid>/editar", methods=["POST"])
@cliente_required
def editar_bicicleta(bid):
    uid = session["usuario"]["id"]
    marca       = request.form.get("marca","").strip()
    modelo      = request.form.get("modelo","").strip()
    color       = request.form.get("color","").strip()
    anio        = request.form.get("anio") or None
    tipo        = request.form.get("tipo","Urbana")
    descripcion = request.form.get("descripcion","").strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "UPDATE bicicletas SET marca=%s, modelo=%s, color=%s, anio=%s, tipo=%s, descripcion=%s WHERE id=%s AND cliente_id=%s",
        (marca, modelo, color, anio, tipo, descripcion, bid, uid)
    )
    conn.commit(); cur.close(); conn.close()
    flash("Bicicleta actualizada correctamente.", "success")
    return redirect("/mis-bicicletas")

@app.route("/mis-bicicletas/<int:bid>/eliminar", methods=["POST"])
@login_required
def eliminar_bicicleta(bid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM bicicletas WHERE id=%s AND cliente_id=%s", (bid, session["usuario"]["id"]))
    conn.commit(); cur.close(); conn.close()
    flash("Bicicleta eliminada","success")
    return redirect("/mis-bicicletas")

@app.route("/cancelar-orden/<int:oid>", methods=["POST"])
@login_required
def cancelar_orden(oid):
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    # Solo el cliente dueño puede cancelar, y solo si está pendiente o asignada
    cur.execute("""SELECT id, estado FROM ordenes
                   WHERE id=%s AND cliente_id=%s
                   AND estado IN ('pendiente','asignada')""", (oid, uid))
    orden = cur.fetchone()
    if orden:
        cur.execute("UPDATE ordenes SET estado='cancelada' WHERE id=%s", (oid,))
        conn.commit()
        flash("Orden cancelada correctamente.", "success")
    else:
        flash("No se puede cancelar esta orden. Solo puedes cancelar ordenes pendientes o asignadas.", "error")
    cur.close(); conn.close()
    return redirect("/mis-ordenes")

@app.route("/calificar/<int:oid>", methods=["POST"])
@login_required
def calificar(oid):
    uid  = session["usuario"]["id"]
    pun  = int(request.form.get("puntuacion","5"))
    com  = request.form.get("comentario","").strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT mecanico_id FROM ordenes WHERE id=%s AND cliente_id=%s AND estado='completada'", (oid,uid))
    o = cur.fetchone()
    if o:
        cur.execute("INSERT IGNORE INTO calificaciones (orden_id,mecanico_id,cliente_id,puntuacion,comentario) VALUES (%s,%s,%s,%s,%s)",
            (oid, o["mecanico_id"], uid, pun, com))
        if o["mecanico_id"]:
            cur.execute("""UPDATE mecanicos SET calificacion_promedio=(
                SELECT AVG(puntuacion) FROM calificaciones WHERE mecanico_id=%s)
                WHERE usuario_id=%s""", (o["mecanico_id"], o["mecanico_id"]))
        conn.commit()
        flash("Calificacion enviada. Gracias por tu opinion!","success")
    cur.close(); conn.close()
    return redirect("/mis-ordenes")

# ─── MECÁNICO ─────────────────────────────────────────────────
@app.route("/mecanico/pausa", methods=["POST"])
@login_required
@mecanico_required
def mecanico_pausa():
    from datetime import datetime, timedelta
    uid    = session["usuario"]["id"]
    minutos= int(request.form.get("minutos", 60))
    motivo = request.form.get("motivo", "Pausa").strip() or "Pausa"
    minutos= max(15, min(minutos, 240))  # entre 15 min y 4 horas
    ahora  = now_col()
    fin    = ahora + timedelta(minutes=minutos)
    conn = get_db(); cur = conn.cursor()
    # Desactivar pausas anteriores activas
    cur.execute("UPDATE pausas_mecanico SET activa=0 WHERE mecanico_id=%s AND activa=1", (uid,))
    # Crear nueva pausa
    cur.execute("INSERT INTO pausas_mecanico (mecanico_id,motivo,inicio,fin,activa) VALUES (%s,%s,%s,%s,1)",
                (uid, motivo, ahora, fin))
    # Marcar mecánico como ocupado
    cur.execute("UPDATE mecanicos SET estado_mecanico='ocupado' WHERE usuario_id=%s", (uid,))
    conn.commit(); cur.close(); conn.close()
    flash(f"Pausa activada por {minutos} minutos. Regregas a las {fin.strftime('%H:%M')}.", "success")
    return redirect("/mecanico")

@app.route("/mecanico/pausa/cancelar", methods=["POST"])
@login_required
@mecanico_required
def mecanico_cancelar_pausa():
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pausas_mecanico SET activa=0 WHERE mecanico_id=%s AND activa=1", (uid,))
    cur.execute("UPDATE mecanicos SET estado_mecanico='disponible' WHERE usuario_id=%s", (uid,))
    conn.commit(); cur.close(); conn.close()
    flash("Pausa cancelada. Ya estas disponible.", "success")
    return redirect("/mecanico")

@app.route("/mecanico/pausa/programar", methods=["POST"])
@login_required
@mecanico_required
def mecanico_programar_pausa():
    """Programa una pausa futura en el calendario del mecánico."""
    from datetime import datetime
    uid    = session["usuario"]["id"]
    motivo = request.form.get("motivo", "Pausa").strip() or "Pausa"
    fecha  = request.form.get("fecha", "").strip()
    hora_i = request.form.get("hora_inicio", "").strip()
    hora_f = request.form.get("hora_fin", "").strip()
    if not fecha or not hora_i or not hora_f:
        flash("Debes indicar fecha, hora de inicio y hora de fin.", "error")
        return redirect("/mecanico")
    try:
        inicio = datetime.strptime(f"{fecha} {hora_i}", "%Y-%m-%d %H:%M")
        fin    = datetime.strptime(f"{fecha} {hora_f}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Formato de fecha u hora invalido.", "error")
        return redirect("/mecanico")
    if fin <= inicio:
        flash("La hora de fin debe ser despues de la hora de inicio.", "error")
        return redirect("/mecanico")
    if inicio < now_col():
        flash("No puedes programar pausas en el pasado.", "error")
        return redirect("/mecanico")
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO pausas_mecanico (mecanico_id,motivo,inicio,fin,activa) VALUES (%s,%s,%s,%s,0)",
        (uid, motivo, inicio, fin)
    )
    conn.commit(); cur.close(); conn.close()
    flash(f"Pausa programada para el {inicio.strftime('%d/%m/%Y')} de {hora_i} a {hora_f}.", "success")
    return redirect("/mecanico")

@app.route("/mecanico/pausa/eliminar/<int:pausa_id>", methods=["POST"])
@login_required
@mecanico_required
def mecanico_eliminar_pausa(pausa_id):
    """Elimina una pausa programada que aun no esta activa."""
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "DELETE FROM pausas_mecanico WHERE id=%s AND mecanico_id=%s AND activa=0 AND inicio > NOW()",
        (pausa_id, uid)
    )
    conn.commit(); cur.close(); conn.close()
    flash("Pausa eliminada del calendario.", "success")
    return redirect("/mecanico")

@app.route("/api/pausas-mecanico/<int:mec_id>")
@login_required
def api_pausas_mecanico(mec_id):
    """Devuelve pausas programadas del mecanico para bloquearlas en el calendario del cliente."""
    from flask import jsonify
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT DATE_FORMAT(inicio,'%%Y-%%m-%%d') as fecha,
               TIME_FORMAT(inicio,'%%H:%%i') as hora_inicio,
               TIME_FORMAT(fin,'%%H:%%i') as hora_fin,
               motivo,
               TIMESTAMPDIFF(MINUTE, inicio, fin) as duracion_mins
        FROM pausas_mecanico
        WHERE mecanico_id = %s
          AND fin > NOW()
          AND inicio <= DATE_ADD(NOW(), INTERVAL 90 DAY)
        ORDER BY inicio ASC
    """, (mec_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/mecanico")
@login_required
@mecanico_required
def mecanico_dashboard():
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre, u.nombre as cliente_nombre,
        u.telefono as cliente_telefono FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id JOIN usuarios u ON o.cliente_id=u.id
        WHERE o.mecanico_id=%s AND o.estado NOT IN ('completada','cancelada')
        ORDER BY o.fecha_servicio ASC""", (uid,))
    ordenes = cur.fetchall()
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE mecanico_id=%s AND DATE(fecha_servicio)=CURDATE()", (uid,))
    hoy = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE mecanico_id=%s AND estado IN ('pendiente','asignada','en_camino','proceso')", (uid,))
    pend = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE mecanico_id=%s AND estado='completada' AND DATE(fecha_solicitud)=CURDATE()", (uid,))
    comp = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(calificacion_promedio,0) as c FROM mecanicos WHERE usuario_id=%s", (uid,))
    cal_row = cur.fetchone()
    cal = round(float(cal_row["c"]),1) if cal_row else 0
    # Pausa activa del mecánico
    from datetime import datetime as _dt
    cur.execute("""SELECT * FROM pausas_mecanico
                   WHERE mecanico_id=%s AND activa=1 AND fin > NOW()
                   ORDER BY fin DESC LIMIT 1""", (uid,))
    pausa_activa = cur.fetchone()
    # Si la pausa ya venció, desactivarla automáticamente
    cur.execute("""UPDATE pausas_mecanico SET activa=0
                   WHERE mecanico_id=%s AND activa=1 AND fin <= NOW()""", (uid,))
    if cur.rowcount > 0:
        cur.execute("UPDATE mecanicos SET estado_mecanico='disponible' WHERE usuario_id=%s", (uid,))
        pausa_activa = None
    # Pausas programadas futuras (activa=0, aún no han comenzado)
    cur.execute("""SELECT id, motivo,
                   DATE_FORMAT(inicio,'%%d/%%m/%%Y') as fecha_fmt,
                   TIME_FORMAT(inicio,'%%H:%%i') as hora_inicio,
                   TIME_FORMAT(fin,'%%H:%%i') as hora_fin,
                   DATE_FORMAT(inicio,'%%Y-%%m-%%d') as fecha_iso
                   FROM pausas_mecanico
                   WHERE mecanico_id=%s AND activa=0 AND inicio > NOW()
                   ORDER BY inicio ASC""", (uid,))
    pausas_programadas = cur.fetchall()
    conn.commit()
    cur.close(); conn.close()
    stats = {"hoy":hoy,"pendientes":pend,"completadas":comp,"calificacion":cal}
    return render_template("mecanico/dashboard.html", ordenes=ordenes, stats=stats,
                           pausa_activa=pausa_activa, pausas_programadas=pausas_programadas)

@app.route("/mecanico/orden/<int:oid>")
@login_required
@mecanico_required
def mecanico_orden(oid):
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre, u.nombre as cliente_nombre,
        u.telefono as cliente_telefono, b.marca as bici_marca, b.modelo as bici_modelo,
        b.color as bici_color, b.tipo as bici_tipo
        FROM ordenes o JOIN servicios s ON o.servicio_id=s.id
        JOIN usuarios u ON o.cliente_id=u.id
        LEFT JOIN bicicletas b ON o.bici_id=b.id
        WHERE o.id=%s AND o.mecanico_id=%s""", (oid, uid))
    orden = cur.fetchone(); cur.close(); conn.close()
    if not orden:
        flash("Orden no encontrada","error"); return redirect("/mecanico")
    return render_template("mecanico/orden.html", orden=orden)

@app.route("/mecanico/orden/<int:oid>/estado", methods=["POST"])
@login_required
@mecanico_required
def mecanico_actualizar_estado(oid):
    estado = request.form.get("estado")
    obs    = request.form.get("observaciones","")
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE ordenes SET estado=%s, observaciones_mecanico=%s WHERE id=%s AND mecanico_id=%s",
        (estado, obs, oid, session["usuario"]["id"]))
    conn.commit(); cur.close(); conn.close()
    flash(f"Estado actualizado a: {estado}","success")
    return redirect(f"/mecanico/orden/{oid}")

@app.route("/mecanico/historial")
@login_required
@mecanico_required
def mecanico_historial():
    uid = session["usuario"]["id"]
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre, u.nombre as cliente_nombre,
        c.puntuacion as calificacion FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id JOIN usuarios u ON o.cliente_id=u.id
        LEFT JOIN calificaciones c ON c.orden_id=o.id
        WHERE o.mecanico_id=%s ORDER BY o.fecha_solicitud DESC""", (uid,))
    ordenes = cur.fetchall(); cur.close(); conn.close()
    return render_template("mecanico/historial.html", ordenes=ordenes)

# ─── ADMIN ───────────────────────────────────────────────────
@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM usuarios WHERE rol='cliente'"); tc = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM usuarios WHERE rol='mecanico' AND activo=1"); tm = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE DATE(fecha_solicitud)=CURDATE()"); oh = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='pendiente'"); op = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='completada'"); oc = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(SUM(precio_final),0) as s FROM ordenes WHERE estado='completada' AND MONTH(fecha_solicitud)=MONTH(NOW())"); ing = float(cur.fetchone()["s"])
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre, uc.nombre as cliente_nombre,
        um.nombre as mecanico_nombre FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id JOIN usuarios uc ON o.cliente_id=uc.id
        LEFT JOIN usuarios um ON o.mecanico_id=um.id
        ORDER BY o.fecha_solicitud DESC LIMIT 10""")
    ultimas = cur.fetchall()
    cur.execute("""SELECT u.*, m.zona, m.estado_mecanico, m.calificacion_promedio FROM usuarios u
        LEFT JOIN mecanicos m ON m.usuario_id=u.id WHERE u.rol='mecanico' AND u.activo=1 LIMIT 6""")
    mecs = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin/panel.html",
        total_clientes=tc, total_mecanicos=tm, ordenes_hoy=oh,
        ordenes_pendientes=op, ordenes_completadas=oc, ingresos_mes=ing,
        ultimas_ordenes=ultimas, mecanicos=mecs)

@app.route("/admin/usuarios")
@login_required
@admin_required
def admin_usuarios():
    rol = request.args.get("rol", "")
    conn = get_db(); cur = conn.cursor()
    sql = """SELECT u.*, m.zona, m.calificacion_promedio, m.total_servicios, m.estado_mecanico
             FROM usuarios u LEFT JOIN mecanicos m ON m.usuario_id=u.id"""
    if rol:
        sql += " WHERE u.rol=%s ORDER BY u.fecha_registro DESC"
        cur.execute(sql, (rol,))
    else:
        sql += " ORDER BY u.fecha_registro DESC"
        cur.execute(sql)
    us = cur.fetchall()
    # Conteos por rol
    cur.execute("SELECT rol, COUNT(*) as c FROM usuarios GROUP BY rol")
    conteos = {r["rol"]: r["c"] for r in cur.fetchall()}
    cur.close(); conn.close()
    return render_template("admin/usuarios.html", usuarios=us, rol_filtro=rol, conteos=conteos)

@app.route("/admin/usuario/<int:uid>")
@login_required
@admin_required
def admin_ver_usuario(uid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT u.*, m.zona, m.calificacion_promedio, m.total_servicios, m.estado_mecanico
                   FROM usuarios u LEFT JOIN mecanicos m ON m.usuario_id=u.id
                   WHERE u.id=%s""", (uid,))
    u = cur.fetchone()
    if not u: flash("Usuario no encontrado","error"); cur.close(); conn.close(); return redirect("/admin/usuarios")
    # Ordenes del usuario
    if u["rol"] == "cliente":
        cur.execute("""SELECT o.*, s.nombre as servicio_nombre FROM ordenes o
                       JOIN servicios s ON o.servicio_id=s.id
                       WHERE o.cliente_id=%s ORDER BY o.fecha_solicitud DESC LIMIT 10""", (uid,))
    else:
        cur.execute("""SELECT o.*, s.nombre as servicio_nombre, uc.nombre as cliente_nombre
                       FROM ordenes o JOIN servicios s ON o.servicio_id=s.id
                       JOIN usuarios uc ON o.cliente_id=uc.id
                       WHERE o.mecanico_id=%s ORDER BY o.fecha_solicitud DESC LIMIT 10""", (uid,))
    ordenes = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin/usuario_perfil.html", u=u, ordenes=ordenes)

@app.route("/admin/usuario/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_usuario(uid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT activo FROM usuarios WHERE id=%s", (uid,))
    u = cur.fetchone()
    cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (0 if u["activo"] else 1, uid))
    conn.commit(); cur.close(); conn.close()
    flash("Usuario actualizado","success")
    rol = request.args.get("rol","")
    ref = request.referrer or "/admin/usuarios"
    if "/admin/usuario/" in ref and "/toggle" not in ref:
        return redirect(ref)
    return redirect("/admin/usuarios" + (f"?rol={rol}" if rol else ""))

@app.route("/admin/mecanicos")
@login_required
@admin_required
def admin_mecanicos():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT u.*, m.zona, m.calificacion_promedio, m.total_servicios, m.estado_mecanico
        FROM usuarios u LEFT JOIN mecanicos m ON m.usuario_id=u.id
        WHERE u.rol='mecanico' ORDER BY u.fecha_registro DESC""")
    mecs = cur.fetchall(); cur.close(); conn.close()
    return render_template("admin/mecanicos.html", mecanicos=mecs)

@app.route("/admin/ordenes")
@login_required
@admin_required
def admin_ordenes():
    estado = request.args.get("estado","")
    buscar = request.args.get("q","").strip()
    conn = get_db(); cur = conn.cursor()

    # Query enriquecida con tipo_atencion, emergencia, calificacion
    sql = """SELECT o.*, s.nombre as servicio_nombre, s.icono as servicio_icono,
        uc.nombre as cliente_nombre, uc.apellido as cliente_apellido, uc.rol as cliente_rol,
        um.nombre as mecanico_nombre, um.rol as mecanico_rol,
        cal.puntuacion as calificacion
        FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id
        JOIN usuarios uc ON o.cliente_id=uc.id
        LEFT JOIN usuarios um ON o.mecanico_id=um.id
        LEFT JOIN calificaciones cal ON cal.orden_id=o.id"""
    conds = []
    params = []
    if estado:
        conds.append("o.estado=%s"); params.append(estado)
    if buscar:
        conds.append("(uc.nombre LIKE %s OR uc.apellido LIKE %s OR s.nombre LIKE %s OR um.nombre LIKE %s)")
        like = f"%{buscar}%"
        params += [like, like, like, like]
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY o.fecha_solicitud DESC"
    cur.execute(sql, params)
    ordenes = cur.fetchall()

    # KPIs rápidos
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='pendiente'");   op  = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='completada'");  oc  = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='asignada' OR estado='proceso' OR estado='en_camino'"); oa = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE DATE(fecha_solicitud)=CURDATE()"); oh = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes"); total = cur.fetchone()["c"]
    cur.close(); conn.close()
    from datetime import date as _date
    return render_template("admin/ordenes.html",
        ordenes=ordenes, ordenes_pendientes=op,
        ordenes_completadas=oc, ordenes_activas=oa,
        ordenes_hoy=oh, total_ordenes=total,
        filtro_estado=estado, filtro_buscar=buscar,
        now_date=str(_date.today()))

@app.route("/admin/orden/<int:oid>")
@login_required
@admin_required
def admin_orden_detalle(oid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("""SELECT o.*, s.nombre as servicio_nombre FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id WHERE o.id=%s""", (oid,))
    orden = cur.fetchone()
    cur.execute("SELECT id,nombre,apellido FROM usuarios WHERE rol='mecanico' AND activo=1")
    mecs = cur.fetchall()
    cur.close(); conn.close()
    if not orden: flash("Orden no encontrada","error"); return redirect("/admin/ordenes")
    return render_template("admin/ordenes.html", orden=orden, mecanicos_disponibles=mecs, ordenes=[], ordenes_pendientes=0)

@app.route("/admin/orden/<int:oid>/asignar", methods=["POST"])
@login_required
@admin_required
def admin_asignar_mecanico(oid):
    mid = request.form.get("mecanico_id")
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE ordenes SET mecanico_id=%s, estado='asignada' WHERE id=%s", (mid, oid))
    conn.commit(); cur.close(); conn.close()
    flash("Mecanico asignado exitosamente","success")
    return redirect("/admin/ordenes")

@app.route("/admin/servicios")
@login_required
@admin_required
def admin_servicios():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM servicios ORDER BY id")
    svcs = cur.fetchall(); cur.close(); conn.close()
    return render_template("admin/servicios.html", servicios=svcs)

@app.route("/admin/servicio/nuevo", methods=["POST"])
@login_required
@admin_required
def admin_nuevo_servicio():
    nombre = request.form.get("nombre","").strip()
    desc   = request.form.get("descripcion","").strip()
    icono  = request.form.get("icono","🔧").strip()
    pmin   = request.form.get("precio_min",10)
    pmax   = request.form.get("precio_max",50)
    tiempo = request.form.get("tiempo_estimado","45 min").strip()
    if not nombre: flash("El nombre es obligatorio","error"); return redirect("/admin/servicios")
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO servicios (nombre,descripcion,icono,precio_min,precio_max,tiempo_estimado) VALUES (%s,%s,%s,%s,%s,%s)",
        (nombre,desc,icono,pmin,pmax,tiempo))
    conn.commit(); cur.close(); conn.close()
    flash("Servicio creado exitosamente","success")
    return redirect("/admin/servicios")

@app.route("/admin/servicio/<int:sid>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_servicio(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT activo FROM servicios WHERE id=%s", (sid,))
    s = cur.fetchone()
    cur.execute("UPDATE servicios SET activo=%s WHERE id=%s", (0 if s["activo"] else 1, sid))
    conn.commit(); cur.close(); conn.close()
    flash("Servicio actualizado","success")
    return redirect("/admin/servicios")

@app.route("/admin/reportes")
@login_required
@admin_required
def admin_reportes():
    import json as _json
    conn = get_db(); cur = conn.cursor()

    # KPIs principales
    cur.execute("SELECT COALESCE(SUM(precio_final),0) as s FROM ordenes WHERE estado='completada'")
    ti = float(cur.fetchone()["s"])
    cur.execute("SELECT COUNT(*) as c FROM ordenes"); to = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(AVG(puntuacion),0) as a FROM calificaciones")
    pc = round(float(cur.fetchone()["a"]),1)
    cur.execute("SELECT COUNT(*) as c FROM usuarios WHERE rol='cliente' AND MONTH(fecha_registro)=MONTH(NOW())")
    cn = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='completada'")
    oc = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM ordenes WHERE estado='pendiente'")
    op = cur.fetchone()["c"]

    # Tasa de completado
    tasa = round((oc / to * 100), 1) if to > 0 else 0

    # Servicios top
    cur.execute("""SELECT s.nombre, COUNT(*) as total FROM ordenes o
        JOIN servicios s ON o.servicio_id=s.id GROUP BY s.id ORDER BY total DESC LIMIT 5""")
    svcs_top = cur.fetchall()
    max_s = max([s["total"] for s in svcs_top]) if svcs_top else 1

    # Mecánicos top
    cur.execute("""SELECT u.nombre, COUNT(o.id) as total_servicios,
        COALESCE(AVG(c.puntuacion),0) as calificacion
        FROM usuarios u LEFT JOIN ordenes o ON o.mecanico_id=u.id
        LEFT JOIN calificaciones c ON c.mecanico_id=u.id
        WHERE u.rol='mecanico' GROUP BY u.id ORDER BY total_servicios DESC LIMIT 5""")
    mecs_top = cur.fetchall()
    for m in mecs_top: m["calificacion"] = round(float(m["calificacion"]),1)

    # Distribución de estados (para dona)
    cur.execute("""SELECT estado, COUNT(*) as total FROM ordenes GROUP BY estado""")
    estados_raw = cur.fetchall()
    estados_labels = [r["estado"].replace("_"," ").capitalize() for r in estados_raw]
    estados_data   = [r["total"] for r in estados_raw]

    # Ingresos por mes (últimos 6 meses) — para línea
    cur.execute("""
        SELECT DATE_FORMAT(fecha_solicitud,'%b %Y') as mes,
               MONTH(fecha_solicitud) as nmes,
               YEAR(fecha_solicitud) as anio,
               COALESCE(SUM(precio_final),0) as ingresos,
               COUNT(*) as ordenes
        FROM ordenes WHERE estado='completada'
              AND fecha_solicitud >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY YEAR(fecha_solicitud), MONTH(fecha_solicitud), DATE_FORMAT(fecha_solicitud,'%b %Y')
        ORDER BY YEAR(fecha_solicitud), MONTH(fecha_solicitud)
    """)
    ingresos_mes = cur.fetchall()
    meses_labels   = [r["mes"] for r in ingresos_mes]
    meses_ingresos = [float(r["ingresos"]) for r in ingresos_mes]
    meses_ordenes  = [r["ordenes"] for r in ingresos_mes]

    # Tipo de atención (taller/domicilio/recogida) — para radar o barras
    cur.execute("""SELECT tipo_atencion, COUNT(*) as total FROM ordenes
                   GROUP BY tipo_atencion""")
    tipos_raw = cur.fetchall()
    tipos_labels = [r["tipo_atencion"].capitalize() if r["tipo_atencion"] else "Taller" for r in tipos_raw]
    tipos_data   = [r["total"] for r in tipos_raw]

    # Ticket promedio por servicio
    cur.execute("""SELECT s.nombre, ROUND(AVG(o.precio_final),0) as promedio
        FROM ordenes o JOIN servicios s ON o.servicio_id=s.id
        WHERE o.estado='completada' GROUP BY s.id ORDER BY promedio DESC LIMIT 5""")
    tickets = cur.fetchall()
    ticket_labels = [r["nombre"] for r in tickets]
    ticket_data   = [float(r["promedio"]) for r in tickets]

    cur.close(); conn.close()
    return render_template("admin/reportes.html",
        total_ingresos=ti, total_ordenes=to,
        promedio_calificacion=pc, clientes_nuevos=cn,
        ordenes_completadas=oc, ordenes_pendientes=op, tasa_completado=tasa,
        servicios_top=svcs_top, max_servicios=max_s, mecanicos_top=mecs_top,
        estados_labels=_json.dumps(estados_labels),
        estados_data=_json.dumps(estados_data),
        meses_labels=_json.dumps(meses_labels),
        meses_ingresos=_json.dumps(meses_ingresos),
        meses_ordenes=_json.dumps(meses_ordenes),
        tipos_labels=_json.dumps(tipos_labels),
        tipos_data=_json.dumps(tipos_data),
        ticket_labels=_json.dumps(ticket_labels),
        ticket_data=_json.dumps(ticket_data)
    )

# ─── PERFIL ──────────────────────────────────────────────────
@app.route("/perfil")
@login_required
def perfil():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE id=%s", (session["usuario"]["id"],))
    u = cur.fetchone(); cur.close(); conn.close()
    return render_template("perfil.html", user=u)

@app.route("/perfil/actualizar", methods=["POST"])
@login_required
def perfil_actualizar():
    n  = request.form.get("nombre","").strip()
    ap = request.form.get("apellido","").strip()
    tf = request.form.get("telefono","").strip()
    ci = request.form.get("ciudad","").strip()
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE usuarios SET nombre=%s, apellido=%s, telefono=%s, ciudad=%s WHERE id=%s",
        (n, ap, tf, ci, session["usuario"]["id"]))
    conn.commit(); cur.close(); conn.close()
    session["usuario"]["nombre"] = n
    flash("Perfil actualizado exitosamente","success")
    return redirect("/perfil")

@app.route("/perfil/cambiar-password", methods=["POST"])
@login_required
def cambiar_password():
    actual   = request.form.get("actual","")
    nueva    = request.form.get("nueva","")
    confirmar= request.form.get("confirmar","")
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT password FROM usuarios WHERE id=%s", (session["usuario"]["id"],))
    u = cur.fetchone()
    if not check_password_hash(u["password"], actual):
        flash("Contrasena actual incorrecta","error")
    elif len(nueva) < 6:
        flash("La nueva contrasena debe tener minimo 6 caracteres","error")
    elif nueva != confirmar:
        flash("Las contrasenas no coinciden","error")
    else:
        cur.execute("UPDATE usuarios SET password=%s WHERE id=%s",
            (generate_password_hash(nueva), session["usuario"]["id"]))
        conn.commit()
        flash("Contrasena actualizada exitosamente","success")
    cur.close(); conn.close()
    return redirect("/perfil")


# ─── NOTIFICACIONES ──────────────────────────────────────────────────────────

def crear_notificacion(usuario_id, tipo, titulo, mensaje):
    """Inserta una notificacion en la BD para un usuario."""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            'INSERT INTO notificaciones (usuario_id, tipo, titulo, mensaje) VALUES (%s,%s,%s,%s)',
            (usuario_id, tipo, titulo, mensaje)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f'[NOTIF ERROR] {e}')


def verificar_mantenimiento_mensual(usuario_id):
    """Si el cliente no ha recibido recordatorio de mantenimiento en 30 dias, crea uno."""
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            'SELECT id FROM notificaciones WHERE usuario_id=%s AND tipo=%s AND fecha >= DATE_SUB(NOW(), INTERVAL 30 DAY) LIMIT 1',
            (usuario_id, 'mantenimiento')
        )
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO notificaciones (usuario_id, tipo, titulo, mensaje) VALUES (%s,%s,%s,%s)',
                (usuario_id, 'mantenimiento',
                 'Recordatorio de mantenimiento',
                 'Han pasado 30 dias desde tu ultimo recordatorio. Te recomendamos agendar un mantenimiento preventivo para mantener tu bicicleta en optimas condiciones.')
            )
            conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print(f'[MANTENIMIENTO ERROR] {e}')



@app.route('/notificaciones')
@cliente_required
def mis_notificaciones():
    verificar_mantenimiento_mensual(session['usuario']['id'])
    return render_template('cliente/mis_notificaciones.html')

@app.route('/api/notificaciones')
@login_required
def api_notificaciones():
    uid = session['usuario']['id']
    if session['usuario']['rol'] == 'cliente':
        verificar_mantenimiento_mensual(uid)
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT id, tipo, titulo, mensaje, leida, fecha FROM notificaciones WHERE usuario_id=%s ORDER BY fecha DESC LIMIT 20', (uid,))
    notifs = cur.fetchall()
    cur.execute('SELECT COUNT(*) as c FROM notificaciones WHERE usuario_id=%s AND leida=0', (uid,))
    no_leidas = cur.fetchone()['c']
    cur.close(); conn.close()
    for n in notifs:
        if hasattr(n['fecha'], 'strftime'):
            n['fecha'] = n['fecha'].strftime('%d/%m/%Y %H:%M')
    return {'notificaciones': notifs, 'no_leidas': no_leidas}


@app.route('/api/notificaciones/leer/<int:nid>', methods=['POST'])
@login_required
def marcar_leida(nid):
    uid = session['usuario']['id']
    conn = get_db(); cur = conn.cursor()
    cur.execute('UPDATE notificaciones SET leida=1 WHERE id=%s AND usuario_id=%s', (nid, uid))
    conn.commit(); cur.close(); conn.close()
    return {'ok': True}


@app.route('/api/notificaciones/leer-todas', methods=['POST'])
@login_required
def marcar_todas_leidas():
    uid = session['usuario']['id']
    conn = get_db(); cur = conn.cursor()
    cur.execute('UPDATE notificaciones SET leida=1 WHERE usuario_id=%s', (uid,))
    conn.commit(); cur.close(); conn.close()
    return {'ok': True}




@app.route('/api/notificaciones/admin-historial')
@admin_required
def api_admin_historial_notif():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT n.tipo, n.titulo, u.nombre, n.fecha
        FROM notificaciones n
        JOIN usuarios u ON u.id = n.usuario_id
        ORDER BY n.fecha DESC LIMIT 30
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    for r in rows:
        if hasattr(r['fecha'], 'strftime'):
            r['fecha'] = r['fecha'].strftime('%d/%m/%Y %H:%M')
    return rows

@app.route('/admin/notificaciones', methods=['GET'])
@admin_required
def admin_notificaciones():
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT id, nombre, apellido, email FROM usuarios WHERE rol=%s AND activo=1 ORDER BY nombre', ('cliente',))
    clientes = cur.fetchall()
    cur.close(); conn.close()
    return render_template('admin/notificaciones.html', clientes=clientes)


@app.route('/admin/notificaciones/enviar', methods=['POST'])
@admin_required
def admin_enviar_notificacion():
    destino = request.form.get('destino')
    titulo  = request.form.get('titulo', '').strip()
    mensaje = request.form.get('mensaje', '').strip()
    if not titulo or not mensaje:
        return {'ok': False, 'error': 'Titulo y mensaje son obligatorios'}, 400
    conn = get_db(); cur = conn.cursor()
    if destino == 'todos':
        cur.execute('SELECT id FROM usuarios WHERE rol=%s AND activo=1', ('cliente',))
        ids = [r['id'] for r in cur.fetchall()]
    else:
        ids = [int(destino)]
    for uid in ids:
        cur.execute('INSERT INTO notificaciones (usuario_id, tipo, titulo, mensaje) VALUES (%s,%s,%s,%s)', (uid, 'manual', titulo, mensaje))
    conn.commit(); cur.close(); conn.close()
    return {'ok': True, 'enviadas': len(ids)}

@app.errorhandler(404)
def not_found(e): return render_template("404.html"), 404

if __name__ == "__main__":
    import os, threading, webbrowser
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False evita que Flask cree un proceso hijo que tambien
    # dispara el timer, lo cual abria el navegador dos veces.
    is_main = os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    if is_main:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)