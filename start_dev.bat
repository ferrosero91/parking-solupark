@echo off
echo ========================================
echo Sistema de Parqueadero - Modo Desarrollo
echo ========================================
echo.

REM Verificar si existe el entorno virtual
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
    echo.
)

REM Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate.bat
echo.

REM Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
echo.

REM Verificar si existe .env
if not exist ".env" (
    echo Creando archivo .env desde .env.example...
    copy .env.example .env
    echo.
)

REM Ejecutar migraciones
echo Ejecutando migraciones...
python manage.py migrate
echo.

REM Iniciar servidor
echo Iniciando servidor de desarrollo...
echo Accede a: http://localhost:8000
echo Presiona Ctrl+C para detener el servidor
echo.
python manage.py runserver
