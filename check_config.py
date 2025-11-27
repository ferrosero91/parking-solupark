#!/usr/bin/env python
"""
Script para verificar la configuración del sistema
"""
import os
import sys
from pathlib import Path

# Agregar el directorio del proyecto al path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

def check_env_var(var_name, required=True):
    """Verifica si una variable de entorno está configurada"""
    value = os.environ.get(var_name)
    if value:
        # Ocultar valores sensibles
        if var_name in ['SECRET_KEY', 'DATABASE_PASSWORD']:
            display_value = f"{value[:10]}..." if len(value) > 10 else "***"
        else:
            display_value = value
        print(f"✓ {var_name}: {display_value}")
        return True
    else:
        if required:
            print(f"✗ {var_name}: NO CONFIGURADO (REQUERIDO)")
        else:
            print(f"○ {var_name}: No configurado (opcional)")
        return not required

def main():
    print("\n" + "="*60)
    print("VERIFICACIÓN DE CONFIGURACIÓN")
    print("="*60 + "\n")
    
    # Variables requeridas
    print("Variables Requeridas:")
    print("-" * 60)
    all_ok = True
    all_ok &= check_env_var('DEBUG')
    all_ok &= check_env_var('SECRET_KEY')
    all_ok &= check_env_var('DATABASE_ENGINE')
    all_ok &= check_env_var('ALLOWED_HOSTS')
    
    print("\n")
    
    # Variables de base de datos
    db_engine = os.environ.get('DATABASE_ENGINE', '')
    if 'postgresql' in db_engine:
        print("Configuración de PostgreSQL:")
        print("-" * 60)
        all_ok &= check_env_var('DATABASE_NAME')
        all_ok &= check_env_var('DATABASE_USER')
        all_ok &= check_env_var('DATABASE_PASSWORD')
        all_ok &= check_env_var('DATABASE_HOST')
        all_ok &= check_env_var('DATABASE_PORT')
    else:
        print("Configuración de SQLite:")
        print("-" * 60)
        all_ok &= check_env_var('DATABASE_NAME')
    
    print("\n")
    
    # Variables opcionales
    print("Variables Opcionales:")
    print("-" * 60)
    check_env_var('RENDER_EXTERNAL_HOSTNAME', required=False)
    check_env_var('REDIS_URL', required=False)
    
    print("\n" + "="*60)
    
    # Verificar modo DEBUG
    debug_mode = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
    if debug_mode:
        print("⚠️  MODO DEBUG ACTIVADO")
        print("   Esto es correcto para desarrollo, pero NO para producción")
    else:
        print("✓ MODO PRODUCCIÓN ACTIVADO")
        print("   Asegúrate de tener todas las variables configuradas")
    
    print("="*60 + "\n")
    
    # Verificar archivo .env
    if Path('.env').exists():
        print("✓ Archivo .env encontrado")
    else:
        print("✗ Archivo .env NO encontrado")
        print("  Copia .env.example a .env y configura las variables")
        all_ok = False
    
    print("\n" + "="*60)
    
    if all_ok:
        print("✓ CONFIGURACIÓN CORRECTA")
        print("  Puedes ejecutar el servidor con: python manage.py runserver")
    else:
        print("✗ CONFIGURACIÓN INCOMPLETA")
        print("  Revisa las variables marcadas con ✗")
    
    print("="*60 + "\n")
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
