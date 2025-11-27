# -*- coding: utf-8 -*-
"""
Comando para migrar usuarios del grupo 'Administrador' al grupo 'Admin'
y asignar permisos correctos
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction


class Command(BaseCommand):
    help = 'Migra usuarios del grupo Administrador al grupo Admin con permisos correctos'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Obtener o crear el grupo Admin
            admin_group, created = Group.objects.get_or_create(name='Admin')
            
            # Asignar todos los permisos de parking al grupo Admin
            permissions = Permission.objects.filter(
                content_type__app_label='parking'
            )
            admin_group.permissions.set(permissions)
            
            self.stdout.write(
                self.style.SUCCESS(f'Grupo Admin configurado con {permissions.count()} permisos')
            )
            
            # Buscar usuarios en el grupo 'Administrador'
            old_admin_group = Group.objects.filter(name='Administrador').first()
            
            if old_admin_group:
                users_to_migrate = old_admin_group.user_set.all()
                
                for user in users_to_migrate:
                    # Remover del grupo antiguo
                    user.groups.remove(old_admin_group)
                    
                    # Agregar al grupo nuevo
                    user.groups.add(admin_group)
                    
                    # Asegurar que es staff
                    user.is_staff = True
                    user.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Usuario {user.username} migrado a grupo Admin')
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Total de usuarios migrados: {users_to_migrate.count()}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('No se encontró el grupo Administrador')
                )
            
            # Verificar usuarios con is_staff=True que no están en ningún grupo
            staff_users = User.objects.filter(is_staff=True, groups__isnull=True)
            
            for user in staff_users:
                user.groups.add(admin_group)
                self.stdout.write(
                    self.style.SUCCESS(f'Usuario staff {user.username} agregado a grupo Admin')
                )
            
            self.stdout.write(
                self.style.SUCCESS('Migración completada exitosamente')
            )
