# -*- coding: utf-8 -*-
"""
Comando para limpiar usuarios duplicados por email
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count


class Command(BaseCommand):
    help = 'Limpia usuarios duplicados por email, manteniendo solo el más reciente'

    def handle(self, *args, **options):
        # Encontrar emails duplicados
        duplicate_emails = (
            User.objects.values('email')
            .annotate(count=Count('id'))
            .filter(count__gt=1, email__isnull=False)
            .exclude(email='')
        )
        
        if not duplicate_emails:
            self.stdout.write(self.style.SUCCESS('No se encontraron emails duplicados'))
            return
        
        for item in duplicate_emails:
            email = item['email']
            users = User.objects.filter(email=email).order_by('date_joined')
            
            self.stdout.write(f'\nEmail duplicado: {email}')
            self.stdout.write(f'Usuarios encontrados: {users.count()}')
            
            # Mantener el más reciente, eliminar los demás
            users_list = list(users)
            user_to_keep = users_list[-1]  # El más reciente
            users_to_delete = users_list[:-1]  # Todos excepto el último
            
            for user in users_to_delete:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Eliminando: {user.username} (ID: {user.id}, Creado: {user.date_joined})'
                    )
                )
                user.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Manteniendo: {user_to_keep.username} (ID: {user_to_keep.id}, Creado: {user_to_keep.date_joined})'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('\n✓ Limpieza completada'))
