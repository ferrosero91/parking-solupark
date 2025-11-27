"""
Comando de gestión para crear backup de la base de datos PostgreSQL
Uso: python manage.py backup_database
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Crea un backup de la base de datos PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Ruta donde guardar el backup (opcional)',
        )

    def handle(self, *args, **options):
        db_settings = settings.DATABASES['default']
        
        if 'postgresql' not in db_settings['ENGINE']:
            self.stdout.write(self.style.ERROR('Este comando solo funciona con PostgreSQL'))
            return
        
        # Configurar variables
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']
        
        # Nombre del archivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = options.get('output') or f'backup_{db_name}_{timestamp}.sql'
        
        # Crear directorio de backups si no existe
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        output_path = os.path.join(backup_dir, output_file)
        
        self.stdout.write(self.style.WARNING(f'Creando backup de la base de datos...'))
        self.stdout.write(f'Base de datos: {db_name}')
        self.stdout.write(f'Host: {db_host}:{db_port}')
        self.stdout.write(f'Archivo: {output_path}')
        
        try:
            # Configurar variable de entorno para la contraseña
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Ejecutar pg_dump
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-F', 'c',  # Formato custom (comprimido)
                '-b',  # Incluir blobs
                '-v',  # Verbose
                '-f', output_path,
                db_name
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Obtener tamaño del archivo
                file_size = os.path.getsize(output_path)
                size_mb = file_size / (1024 * 1024)
                
                self.stdout.write(self.style.SUCCESS(f'\n✓ Backup creado exitosamente!'))
                self.stdout.write(f'Archivo: {output_path}')
                self.stdout.write(f'Tamaño: {size_mb:.2f} MB')
                self.stdout.write(f'\nPara restaurar este backup, ejecuta:')
                self.stdout.write(f'python manage.py restore_database --file={output_file}')
            else:
                self.stdout.write(self.style.ERROR(f'\n✗ Error al crear backup:'))
                self.stdout.write(result.stderr)
                
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('\n✗ pg_dump no encontrado.'))
            self.stdout.write('Asegúrate de tener PostgreSQL instalado y en el PATH')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error: {str(e)}'))
