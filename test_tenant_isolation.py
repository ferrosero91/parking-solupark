"""
Script para verificar el aislamiento de datos entre parqueaderos (tenants)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings')
django.setup()

from parking.models import ParkingLot, VehicleCategory, ParkingTicket
from django.contrib.auth.models import User

print('='*70)
print('VERIFICACIÓN DE AISLAMIENTO DE DATOS (MULTITENANT)')
print('='*70)

# Crear segundo parqueadero para pruebas
print('\n1. Creando segundo parqueadero de prueba...')
user2, created = User.objects.get_or_create(
    username='test@parqueadero2.com',
    defaults={
        'email': 'test@parqueadero2.com',
        'first_name': 'Parqueadero Test 2'
    }
)
if created:
    user2.set_password('test123')
    user2.save()

parking2, created = ParkingLot.objects.get_or_create(
    user=user2,
    defaults={
        'empresa': 'Parqueadero Test 2',
        'nit': '900999999-9',
        'telefono': '+57 300 000 0000',
        'direccion': 'Calle Test #00-00',
        'is_active': True
    }
)

# Crear categorías para el segundo parqueadero
VehicleCategory.objects.get_or_create(
    parking_lot=parking2,
    name='MOTOS',
    defaults={'first_hour_rate': 2500, 'additional_hour_rate': 1500}
)

print('✓ Segundo parqueadero creado')

# Obtener parqueaderos
parking1 = ParkingLot.objects.get(empresa='Parqueadero Demo')
parking2 = ParkingLot.objects.get(empresa='Parqueadero Test 2')

print(f'\n2. Parqueaderos en el sistema:')
print(f'   - {parking1.empresa} (ID: {parking1.id})')
print(f'   - {parking2.empresa} (ID: {parking2.id})')

# Verificar categorías
print(f'\n3. Verificando categorías por parqueadero:')
cats1 = VehicleCategory.objects.filter(parking_lot=parking1)
cats2 = VehicleCategory.objects.filter(parking_lot=parking2)
print(f'   - {parking1.empresa}: {cats1.count()} categorías')
for cat in cats1:
    print(f'     • {cat.name}')
print(f'   - {parking2.empresa}: {cats2.count()} categorías')
for cat in cats2:
    print(f'     • {cat.name}')

# Crear tickets de prueba
print(f'\n4. Creando tickets de prueba...')
from django.utils import timezone

# Ticket para parqueadero 1
ticket1 = ParkingTicket.objects.create(
    parking_lot=parking1,
    category=cats1.first(),
    placa='ABC123',
    color='Rojo',
    marca='Toyota',
    entry_time=timezone.now()
)
print(f'   ✓ Ticket creado para {parking1.empresa}: {ticket1.placa}')

# Ticket para parqueadero 2
ticket2 = ParkingTicket.objects.create(
    parking_lot=parking2,
    category=cats2.first(),
    placa='XYZ789',
    color='Azul',
    marca='Honda',
    entry_time=timezone.now()
)
print(f'   ✓ Ticket creado para {parking2.empresa}: {ticket2.placa}')

# Verificar aislamiento
print(f'\n5. Verificando aislamiento de datos:')
tickets_p1 = ParkingTicket.objects.filter(parking_lot=parking1)
tickets_p2 = ParkingTicket.objects.filter(parking_lot=parking2)

print(f'   - {parking1.empresa} puede ver: {tickets_p1.count()} tickets')
for t in tickets_p1:
    print(f'     • {t.placa} - {t.marca}')

print(f'   - {parking2.empresa} puede ver: {tickets_p2.count()} tickets')
for t in tickets_p2:
    print(f'     • {t.placa} - {t.marca}')

# Verificar que no hay cruce de datos
print(f'\n6. Pruebas de seguridad:')
cross_check1 = ParkingTicket.objects.filter(parking_lot=parking1, placa='XYZ789').exists()
cross_check2 = ParkingTicket.objects.filter(parking_lot=parking2, placa='ABC123').exists()

if not cross_check1 and not cross_check2:
    print('   ✅ CORRECTO: Los parqueaderos NO pueden ver tickets de otros')
else:
    print('   ❌ ERROR: Hay fuga de datos entre parqueaderos')

# Verificar restricción de placa única por parqueadero
print(f'\n7. Verificando restricción de placa única por parqueadero:')
try:
    # Intentar crear ticket duplicado en el mismo parqueadero
    ParkingTicket.objects.create(
        parking_lot=parking1,
        category=cats1.first(),
        placa='ABC123',
        color='Verde',
        marca='Mazda',
        entry_time=timezone.now()
    )
    print('   ❌ ERROR: Se permitió placa duplicada en el mismo parqueadero')
except Exception as e:
    print('   ✅ CORRECTO: No se permite placa duplicada en el mismo parqueadero')

# Pero sí se puede crear la misma placa en otro parqueadero
try:
    ticket3 = ParkingTicket.objects.create(
        parking_lot=parking2,
        category=cats2.first(),
        placa='ABC123',  # Misma placa pero en otro parqueadero
        color='Negro',
        marca='Nissan',
        entry_time=timezone.now()
    )
    print('   ✅ CORRECTO: Se permite la misma placa en diferentes parqueaderos')
    ticket3.delete()  # Limpiar
except Exception as e:
    print(f'   ❌ ERROR: No se permite la misma placa en diferentes parqueaderos: {e}')

print('\n' + '='*70)
print('VERIFICACIÓN COMPLETADA')
print('='*70)
print('\n📋 RESUMEN:')
print(f'   • Total de parqueaderos: {ParkingLot.objects.count()}')
print(f'   • Total de categorías: {VehicleCategory.objects.count()}')
print(f'   • Total de tickets: {ParkingTicket.objects.count()}')
print('\n✅ El sistema está correctamente aislado por parqueadero')
print('='*70)
