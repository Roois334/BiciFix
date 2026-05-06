# 🚲 BiciFix

Plataforma de gestión de talleres de bicicletas para Cundinamarca (Facatativá · Madrid · Mosquera).  
Construida con **Flask + MySQL**.

---

## 🚀 Despliegue en Render + Filess.io

### Paso 1 — Base de datos en Filess.io

1. Entra a https://filess.io y crea una cuenta gratuita.
2. Crea una nueva base de datos → elige **MySQL**.
3. Guarda los datos que te dan: Host, Usuario, Contraseña, Nombre DB, Puerto.
4. En el panel de Filess.io abre el **SQL Editor**.
5. Pega el contenido del archivo `bicifIx.sql` y ejecútalo.

### Paso 2 — Subir a GitHub

```bash
git init
git add .
git commit -m "primer commit - BiciFix"
git remote add origin https://github.com/TU_USUARIO/bicifix.git
git branch -M main
git push -u origin main
```

### Paso 3 — Desplegar en Render

1. Entra a https://render.com → New → Web Service.
2. Conecta tu repo de GitHub.
3. Configura: Runtime Python 3 | Build: pip install -r requirements.txt | Start: gunicorn app:app
4. Agrega las variables de entorno (ver tabla abajo).
5. Clic en Create Web Service.

Variables de entorno en Render:

SECRET_KEY      → clave larga y segura
MYSQL_HOST      → host de Filess.io
MYSQL_USER      → usuario de Filess.io
MYSQL_PASSWORD  → contraseña de Filess.io
MYSQL_DB        → nombre de tu base de datos
MYSQL_PORT      → 3306

---

## 💻 Correr en local

```bash
git clone https://github.com/TU_USUARIO/bicifix.git
cd bicifix
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 🔑 Credenciales de prueba

Admin     → admin@bicifix.com  / admin123
Mecánico  → (ver SQL)          / mecanico123
Cliente   → (ver SQL)          / cliente123
