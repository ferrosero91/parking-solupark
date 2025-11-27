# -*- coding: utf-8 -*-
"""
Comando para asignar usuarios existentes a sus parqueaderos
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from parking.models import ParkingLot, UserParkingLot


class Command(BaseCommand):
    help = 'Asigna usuarios existentes a sus parqueaderos correspondientes'

    def handle(self, *args, **options):
        # Para cada parqueadero, asignar su usuario dueño
        for parking_lot in ParkingLot.objects.all():
            # Verificar si ya existe la asignación
            assignment, created = UserParkingLot.objects.get_or_create(
                user=parking_lot.user,
                parking_lot=parking_lot
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Usuario {parking_lot.user.username} asignado a {parking_lot.empresa}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'- Usuario {parking_lot.user.username} ya estaba asignado a {parking_lot.empresa}'
                    )
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Asignación completada'))
