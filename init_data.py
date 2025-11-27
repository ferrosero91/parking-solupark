import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings')
django.setup()

from parking.models import ParkingLot, VehicleCategory
from django.contrib.auth.models import User

# Crear información de la empresa
parking_lot, created = ParkingLot.objects.get_or_create(
    id=1,
    defaults={
        'empresa': 'SoluPark',
        'nit': '900123456-7',
        'telefono': '+57 311 709 8269',
        'direccion': 'Calle 123 #45-67, Bogotá'
    }
)
if created:
    print('✓ Información de la empresa creada')
else:
    print('✓ Información de la empresa ya existe')

# Crear categorías de vehículos
categories = [
    {
        'name': 'MOTOS',
        'first_hour_rate': 2000,
        'additional_hour_rate': 1000,
        'is_monthly': False
    },
    {
        'name': 'CARROS',
        'first_hour_rate': 3000,
        'additional_hour_rate': 2000,
        'is_monthly': False
    },
    {
        'name': 'CAMIONETAS',
        'first_hour_rate': 4000,
        'additional_hour_rate': 2500,
        'is_monthly': False
    },
    {
        'name': 'MENSUALIDAD MOTOS',
        'first_hour_rate': 0,
        'additional_hour_rate': 0,
        'is_monthly': True,
        'monthly_rate': 80000
    },
    {
        'name': 'MENSUALIDAD CARROS',
        'first_hour_rate': 0,
        'additional_hour_rate': 0,
        'is_monthly': True,
        'monthly_rate': 150000
    }
]

for cat_data in categories:
    category, created = VehicleCategory.objects.get_or_create(
        name=cat_data['name'],
        defaults=cat_data
    )
    if created:
        print(f'✓ Categoría "{cat_data["name"]}" creada')
    else:
        print(f'✓ Categoría "{cat_data["name"]}" ya existe')

# Asignar el usuario admin al grupo Administrador
try:
    from django.contrib.auth.models import Group
    admin_user = User.objects.get(username='admin')
    admin_group = Group.objects.get(name='Administrador')
    admin_user.groups.add(admin_group)
    admin_user.set_password('admin123')
    admin_user.save()
    print('✓ Usuario admin configurado (usuario: admin, contraseña: admin123)')
except Exception as e:
    print(f'⚠ Error al configurar usuario admin: {e}')

print('\n' + '='*60)
print('PROYECTO INICIALIZADO CORRECTAMENTE')
print('='*60)
print('\nCredenciales de acceso:')
print('  Usuario: admin')
print('  Contraseña: admin123')
print('\nPara iniciar el servidor ejecuta:')
print('  venv\\Scripts\\python.exe manage.py runserver')
print('\nLuego abre tu navegador en:')
print('  http://localhost:8000')
print('='*60)
