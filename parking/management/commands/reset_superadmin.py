# -*- coding: utf-8 -*-
"""
Comando para resetear o crear el superadministrador
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Resetea o crea el superadministrador con credenciales conocidas'

    def handle(self, *args, **options):
        username = 'superadmin'
        email = 'superadmin@solupark.com'
        password = 'SoluPark2025!'
        
        try:
            # Intentar obtener el superusuario existente
            user = User.objects.get(username=username)
            user.set_password(password)
            user.email = email
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Contraseña del superadmin actualizada')
            )
        except User.DoesNotExist:
            # Crear nuevo superusuario
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Superadmin creado exitosamente')
            )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═══════════════════════════════════════'))
        self.stdout.write(self.style.SUCCESS('  CREDENCIALES DEL SUPERADMINISTRADOR'))
        self.stdout.write(self.style.SUCCESS('═══════════════════════════════════════'))
        self.stdout.write(f'  Usuario:    {username}')
        self.stdout.write(f'  Contraseña: {password}')
        self.stdout.write(f'  URL:        http://localhost:8000/superadmin/login/')
        self.stdout.write(self.style.SUCCESS('═══════════════════════════════════════'))
        self.stdout.write('')
