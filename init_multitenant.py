import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings')
django.setup()

from parking.models import ParkingLot, VehicleCategory
from django.contrib.auth.models import User, Group

print('='*60)
print('INICIALIZANDO SISTEMA MULTITENANT')
print('='*60)

# Crear grupos
admin_group, created = Group.objects.get_or_create(name='Administrador')
if created:
    print('✓ Grupo "Administrador" creado')
else:
    print('✓ Grupo "Administrador" ya existe')

vendedor_group, created = Group.objects.get_or_create(name='Vendedor')
if created:
    print('✓ Grupo "Vendedor" creado')
else:
    print('✓ Grupo "Vendedor" ya existe')

# Crear superusuario
superuser, created = User.objects.get_or_create(
    username='superadmin',
    defaults={
        'email': 'superadmin@solupark.com',
        'is_superuser': True,
        'is_staff': True,
        'first_name': 'Super',
        'last_name': 'Administrador'
    }
)
if created:
    superuser.set_password('admin123')
    superuser.save()
    print('✓ Superusuario creado (usuario: superadmin, contraseña: admin123)')
else:
    superuser.set_password('admin123')
    superuser.save()
    print('✓ Superusuario actualizado (usuario: superadmin, contraseña: admin123)')

# Crear un parqueadero de ejemplo
demo_user, created = User.objects.get_or_create(
    username='demo@parqueadero.com',
    defaults={
        'email': 'demo@parqueadero.com',
        'first_name': 'Parqueadero Demo'
    }
)
if created:
    demo_user.set_password('demo123')
    demo_user.save()
    demo_user.groups.add(admin_group)
    print('✓ Usuario demo creado (usuario: demo@parqueadero.com, contraseña: demo123)')
else:
    demo_user.set_password('demo123')
    demo_user.save()
    print('✓ Usuario demo actualizado')

# Crear parqueadero demo
parking_lot, created = ParkingLot.objects.get_or_create(
    user=demo_user,
    defaults={
        'empresa': 'Parqueadero Demo',
        'nit': '900123456-7',
        'telefono': '+57 311 709 8269',
        'direccion': 'Calle 123 #45-67, Bogotá',
        'is_active': True
    }
)
if created:
    print('✓ Parqueadero Demo creado')
else:
    print('✓ Parqueadero Demo ya existe')

# Crear categorías para el parqueadero demo
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
        parking_lot=parking_lot,
        name=cat_data['name'],
        defaults=cat_data
    )
    if created:
        print(f'  ✓ Categoría "{cat_data["name"]}" creada')

print('\n' + '='*60)
print('SISTEMA INICIALIZADO CORRECTAMENTE')
print('='*60)
print('\n📋 CREDENCIALES DE ACCESO:\n')
print('🔑 SUPERADMINISTRADOR (Gestión de Parqueaderos):')
print('   Usuario: superadmin')
print('   Contraseña: admin123')
print('   URL: http://localhost:8000/superadmin/')
print()
print('🏢 PARQUEADERO DEMO:')
print('   Usuario: demo@parqueadero.com')
print('   Contraseña: demo123')
print('   URL: http://localhost:8000/')
print()
print('='*60)
print('Para iniciar el servidor ejecuta:')
print('  venv\\Scripts\\python.exe manage.py runserver')
print('='*60)
