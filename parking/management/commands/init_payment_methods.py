from django.core.management.base import BaseCommand
from parking.models import ParkingLot, PaymentMethod


class Command(BaseCommand):
    help = 'Inicializa medios de pago por defecto para todos los parqueaderos'

    def handle(self, *args, **kwargs):
        # Medios de pago por defecto
        default_methods = [
            {
                'nombre': 'Efectivo',
                'descripcion': 'Pago en efectivo',
                'icono': 'fa-money-bill-wave',
                'color': 'success',
                'orden': 1
            },
            {
                'nombre': 'Nequi',
                'descripcion': 'Pago por Nequi',
                'icono': 'fa-mobile-alt',
                'color': 'purple',
                'orden': 2
            },
            {
                'nombre': 'Daviplata',
                'descripcion': 'Pago por Daviplata',
                'icono': 'fa-mobile-alt',
                'color': 'danger',
                'orden': 3
            },
            {
                'nombre': 'Transferencia Bancaria',
                'descripcion': 'Transferencia bancaria',
                'icono': 'fa-university',
                'color': 'primary',
                'orden': 4
            },
            {
                'nombre': 'Tarjeta Débito',
                'descripcion': 'Pago con tarjeta débito',
                'icono': 'fa-credit-card',
                'color': 'info',
                'orden': 5
            },
            {
                'nombre': 'Tarjeta Crédito',
                'descripcion': 'Pago con tarjeta de crédito',
                'icono': 'fa-credit-card',
                'color': 'warning',
                'orden': 6
            },
            {
                'nombre': 'QR',
                'descripcion': 'Pago por código QR',
                'icono': 'fa-qrcode',
                'color': 'primary',
                'orden': 7
            },
        ]

        parking_lots = ParkingLot.objects.all()
        
        for parking_lot in parking_lots:
            self.stdout.write(f'Inicializando medios de pago para: {parking_lot.empresa}')
            
            for method_data in default_methods:
                payment_method, created = PaymentMethod.objects.get_or_create(
                    parking_lot=parking_lot,
                    nombre=method_data['nombre'],
                    defaults={
                        'descripcion': method_data['descripcion'],
                        'icono': method_data['icono'],
                        'color': method_data['color'],
                        'orden': method_data['orden'],
                        'is_active': True
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Creado: {method_data["nombre"]}'))
                else:
                    self.stdout.write(f'  - Ya existe: {method_data["nombre"]}')
        
        self.stdout.write(self.style.SUCCESS('\n¡Medios de pago inicializados correctamente!'))
