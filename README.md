# 🚗 Sistema de Parqueadero - SoluPark

Sistema completo de gestión de parqueaderos con arquitectura multi-tenant, desarrollado en Django.

## 🚀 Características

- ✅ Sistema multi-tenant (múltiples parqueaderos)
- ✅ Gestión de entradas y salidas de vehículos
- ✅ Códigos de barras automáticos
- ✅ Múltiples medios de pago
- ✅ Mensualidades y clientes
- ✅ Reportes y estadísticas
- ✅ Caja y cuadre diario
- ✅ Sistema de suscripciones
- ✅ Panel de superadministrador
- ✅ Seguridad y optimización

## 📋 Requisitos

- Python 3.10 o superior
- PostgreSQL (producción) o SQLite (desarrollo)
- pip y virtualenv

## 🛠️ Instalación Local

### Opción 1: Script Automático (Windows)
```bash
start_dev.bat
```

### Opción 2: Script Automático (Linux/Mac)
```bash
chmod +x start_dev.sh
./start_dev.sh
```

### Opción 3: Manual

1. **Clonar repositorio**
```bash
git clone <url-repositorio>
cd parqueadero
```

2. **Crear entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

5. **Verificar configuración**
```bash
python check_config.py
```

6. **Ejecutar migraciones**
```bash
python manage.py migrate
```

7. **Crear superusuario**
```bash
python manage.py createsuperuser
```

8. **Inicializar datos**
```bash
python manage.py init_payment_methods
```

9. **Iniciar servidor**
```bash
python manage.py runserver
```

10. **Acceder**
```
http://localhost:8000
```

## 🌐 Despliegue en Producción

### Render.com

1. **Crear cuenta en Render**
2. **Conectar repositorio de GitHub**
3. **Configurar variables de entorno en Render:**
   - `DEBUG=False`
   - `SECRET_KEY=<generar-con-generate_secret_key.py>`
   - `DATABASE_ENGINE=django.db.backends.postgresql`
   - `DATABASE_NAME=<nombre-db>`
   - `DATABASE_USER=<usuario-db>`
   - `DATABASE_PASSWORD=<password-db>`
   - `DATABASE_HOST=<host-db>`
   - `DATABASE_PORT=5432`
   - `ALLOWED_HOSTS=<tu-app>.onrender.com`
   - `RENDER_EXTERNAL_HOSTNAME=<tu-app>.onrender.com`

4. **Build Command:**
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

5. **Start Command:**
```bash
gunicorn parking_system.wsgi:application
```

### VPS Manual

```bash
# Clonar repositorio
git clone <url> /var/www/parking-system
cd /var/www/parking-system

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar .env
cp .env.production.example .env
nano .env  # Editar con valores de producción

# Ejecutar migraciones
python manage.py migrate
python manage.py collectstatic --noinput

# Configurar Gunicorn y Nginx
# Ver documentación de Django para detalles
```

## 🔧 Variables de Entorno

### Desarrollo
```env
DEBUG=True
SECRET_KEY=clave-desarrollo
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Producción
```env
DEBUG=False
SECRET_KEY=<generar-clave-segura>
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=nombre_db
DATABASE_USER=usuario
DATABASE_PASSWORD=contraseña
DATABASE_HOST=host.ejemplo.com
DATABASE_PORT=5432
ALLOWED_HOSTS=tu-dominio.com
RENDER_EXTERNAL_HOSTNAME=tu-app.onrender.com
REDIS_URL=redis://...  # Opcional
```

## 🧪 CI/CD con GitHub Actions

El proyecto incluye workflows automáticos:

### ✅ CI - Tests y Validaciones
- Ejecuta en cada push y PR
- Tests con PostgreSQL
- Linting (Flake8, Black, isort)
- Análisis de seguridad (Bandit, Safety)
- Verificación de deployment

### 🚀 Deploy a Producción
- Se ejecuta en push a `main`
- Deploy automático a Render
- Verificación de salud del servicio
- Creación de releases

### 🧪 Deploy a Staging
- Se ejecuta en push a `develop`
- Deploy a ambiente de staging
- Tests automáticos

### 🔒 CodeQL Security Analysis
- Análisis de seguridad semanal
- Detección de vulnerabilidades

### 📦 Backup Automático
- Backup diario de base de datos
- Retención de 30 días

## 📝 Comandos Útiles

### Desarrollo
```bash
# Verificar configuración
python check_config.py

# Generar SECRET_KEY
python generate_secret_key.py

# Ejecutar tests
python manage.py test

# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Recolectar estáticos
python manage.py collectstatic
```

### Base de Datos
```bash
# Crear superusuario
python manage.py createsuperuser

# Shell de Django
python manage.py shell

# Resetear superadmin
python manage.py reset_superadmin

# Limpiar usuarios duplicados
python manage.py clean_duplicate_users
```

### Producción
```bash
# Iniciar con Gunicorn
gunicorn parking_system.wsgi:application --workers 4

# Verificar deployment
python manage.py check --deploy

# Limpiar sesiones
python manage.py clearsessions
```

## 🏗️ Arquitectura

```
parking_system/
├── parking/                 # App principal
│   ├── models.py           # Modelos de datos
│   ├── views.py            # Vistas principales
│   ├── services.py         # Lógica de negocio
│   ├── utils.py            # Utilidades
│   ├── forms.py            # Formularios
│   ├── middleware.py       # Middleware multi-tenant
│   ├── backends.py         # Backend de autenticación
│   └── templates/          # Templates HTML
├── parking_system/         # Configuración del proyecto
│   ├── settings.py         # Configuración
│   ├── urls.py             # URLs principales
│   └── wsgi.py             # WSGI
├── .github/workflows/      # GitHub Actions
├── static/                 # Archivos estáticos
├── media/                  # Archivos subidos
├── requirements.txt        # Dependencias
├── .env                    # Variables de entorno
└── manage.py               # CLI de Django
```

## 🔐 Seguridad

- ✅ HTTPS obligatorio en producción
- ✅ HSTS habilitado
- ✅ Cookies seguras
- ✅ CSRF protection
- ✅ XSS protection
- ✅ Clickjacking protection
- ✅ SQL injection protection (ORM)
- ✅ Validación de entrada
- ✅ Autenticación multi-tenant
- ✅ Análisis de seguridad automático

## 📊 Optimizaciones

- ✅ Caché de consultas frecuentes
- ✅ Select_related y prefetch_related
- ✅ Índices en base de datos
- ✅ Compresión de archivos estáticos
- ✅ Lazy loading de imágenes
- ✅ Agregaciones en base de datos
- ✅ Transacciones atómicas

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es privado y confidencial.

## 👥 Autores

- Desarrollador Principal - Sistema de Parqueadero

## 🆘 Soporte

Para soporte, contacta al equipo de desarrollo.

## 📚 Documentación Adicional

- [Django Documentation](https://docs.djangoproject.com/)
- [Render Deployment](https://render.com/docs)
- [GitHub Actions](https://docs.github.com/en/actions)
