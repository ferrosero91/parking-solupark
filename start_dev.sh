#!/bin/bash

echo "========================================"
echo "Sistema de Parqueadero - Modo Desarrollo"
echo "========================================"
echo ""

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
    echo ""
fi

# Activar entorno virtual
echo "Activando entorno virtual..."
source venv/bin/activate
echo ""

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt
echo ""

# Verificar si existe .env
if [ ! -f ".env" ]; then
    echo "Creando archivo .env desde .env.example..."
    cp .env.example .env
    echo ""
fi

# Ejecutar migraciones
echo "Ejecutando migraciones..."
python manage.py migrate
echo ""

# Iniciar servidor
echo "Iniciando servidor de desarrollo..."
echo "Accede a: http://localhost:8000"
echo "Presiona Ctrl+C para detener el servidor"
echo ""
python manage.py runserver
