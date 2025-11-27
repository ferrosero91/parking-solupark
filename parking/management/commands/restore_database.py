"""
Comando de gestión para restaurar backup de la base de datos PostgreSQL
Uso: python manage.py restore_database --file=backup.sql
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import os


class Command(BaseCommand):
    help = 'Restaura un backup de la base de datos PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Archivo de backup a restaurar',
        )
        parser.add_argument(
            '--no-backup',
            action='store_true',
            help='No crear backup antes de restaurar',
        )

    def handle(self, *args, **options):
        db_settings = settings.DATABASES['default']
        
        if 'postgresql' not in db_settings['ENGINE']:
            self.stdout.write(self.style.ERROR('Este comando solo funciona con PostgreSQL'))
            return
        
        backup_file = options['file']
        
        # Si no es ruta absoluta, buscar en directorio de backups
        if not os.path.isabs(backup_file):
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            backup_file = os.path.join(backup_dir, backup_file)
        
        if not os.path.exists(backup_file):
            self.stdout.write(self.style.ERROR(f'Archivo no encontrado: {backup_file}'))
            return
        
        # Configurar variables
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('ADVERTENCIA: Esta operación reemplazará la base de datos actual'))
        self.stdout.write(self.style.WARNING('='*60))
        self.stdout.write(f'\nBase de datos: {db_name}')
        self.stdout.write(f'Host: {db_host}:{db_port}')
        self.stdout.write(f'Archivo: {backup_file}')
        
        # Confirmar
        confirm = input('\n¿Deseas continuar? (escribe "SI" para confirmar): ')
        if confirm != 'SI':
            self.stdout.write(self.style.WARNING('Operación cancelada'))
            return
        
        try:
            # Crear backup actual si no se especifica --no-backup
            if not options['no_backup']:
                self.stdout.write(self.style.WARNING('\nCreando backup de seguridad...'))
                from django.core.management import call_command
                call_command('backup_database')
            
            # Configurar variable de entorno para la contraseña
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            self.stdout.write(self.style.WARNING('\nRestaurando base de datos...'))
            
            # Ejecutar pg_restore
            cmd = [
                'pg_restore',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', db_name,
                '-c',  # Limpiar (drop) objetos antes de recrearlos
                '-v',  # Verbose
                backup_file
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('\n✓ Base de datos restaurada exitosamente!'))
                self.stdout.write(self.style.WARNING('\nIMPORTANTE: Reinicia el servidor Django para aplicar los cambios'))
            else:
                # pg_restore puede retornar código de error incluso si la restauración fue exitosa
                # debido a warnings. Verificar el stderr para errores reales
                if 'ERROR' in result.stderr:
                    self.stdout.write(self.style.ERROR('\n✗ Error al restaurar:'))
                    self.stdout.write(result.stderr)
                else:
                    self.stdout.write(self.style.SUCCESS('\n✓ Base de datos restaurada con advertencias'))
                    self.stdout.write(self.style.WARNING('Advertencias:'))
                    self.stdout.write(result.stderr)
                    self.stdout.write(self.style.WARNING('\nIMPORTANTE: Reinicia el servidor Django'))
                
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('\n✗ pg_restore no encontrado.'))
            self.stdout.write('Asegúrate de tener PostgreSQL instalado y en el PATH')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error: {str(e)}'))
