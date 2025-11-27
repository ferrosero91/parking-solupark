"""
Servicio de backup y restauración de datos
"""
import json
import os
from datetime import datetime
from django.core import serializers
from django.conf import settings
from django.db import connection
from .models import (
    ParkingLot, VehicleCategory, ParkingTicket, 
    Cliente, Mensualidad, PaymentMethod, UserParkingLot
)


class BackupService:
    """Servicio para crear y restaurar backups"""
    
    @staticmethod
    def export_parking_lot_data(parking_lot_id):
        """
        Exporta todos los datos de un parqueadero específico
        Retorna un diccionario con los datos en formato JSON
        """
        try:
            parking_lot = ParkingLot.objects.get(id=parking_lot_id)
            
            # Obtener todos los datos relacionados
            data = {
                'metadata': {
                    'backup_date': datetime.now().isoformat(),
                    'parking_lot_id': parking_lot_id,
                    'parking_lot_name': parking_lot.empresa,
                    'version': '1.0'
                },
                'parking_lot': json.loads(serializers.serialize('json', [parking_lot]))[0],
                'categories': json.loads(serializers.serialize('json', 
                    VehicleCategory.objects.filter(parking_lot=parking_lot))),
                'tickets': json.loads(serializers.serialize('json', 
                    ParkingTicket.objects.filter(parking_lot=parking_lot))),
                'clientes': json.loads(serializers.serialize('json', 
                    Cliente.objects.filter(parking_lot=parking_lot))),
                'mensualidades': json.loads(serializers.serialize('json', 
                    Mensualidad.objects.filter(parking_lot=parking_lot))),
                'payment_methods': json.loads(serializers.serialize('json', 
                    PaymentMethod.objects.filter(parking_lot=parking_lot))),
                'user_assignments': json.loads(serializers.serialize('json', 
                    UserParkingLot.objects.filter(parking_lot=parking_lot)))
            }
            
            return {
                'success': True,
                'data': data,
                'filename': f'backup_{parking_lot.empresa}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            }
            
        except ParkingLot.DoesNotExist:
            return {
                'success': False,
                'error': 'Parqueadero no encontrado'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def export_full_database():
        """
        Exporta toda la base de datos
        """
        try:
            # Determinar el tipo de base de datos
            db_engine = settings.DATABASES['default']['ENGINE']
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if 'sqlite' in db_engine:
                # Para SQLite, simplemente copiar el archivo
                db_path = settings.DATABASES['default']['NAME']
                backup_filename = f'full_backup_{timestamp}.sqlite3'
                
                return {
                    'success': True,
                    'type': 'sqlite',
                    'source_path': str(db_path),
                    'filename': backup_filename
                }
                
            elif 'postgresql' in db_engine:
                # Para PostgreSQL, usar comando de gestión
                from django.core.management import call_command
                from io import StringIO
                
                backup_filename = f'full_backup_{timestamp}.sql'
                
                # Ejecutar comando de backup
                try:
                    out = StringIO()
                    call_command('backup_database', '--output', backup_filename, stdout=out)
                    
                    # Obtener ruta del archivo creado
                    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
                    backup_path = os.path.join(backup_dir, backup_filename)
                    
                    return {
                        'success': True,
                        'type': 'postgresql',
                        'filename': backup_filename,
                        'path': backup_path,
                        'message': 'Backup de PostgreSQL creado exitosamente'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Error al crear backup de PostgreSQL: {str(e)}'
                    }
            
            else:
                return {
                    'success': False,
                    'error': 'Tipo de base de datos no soportado'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def restore_full_database(backup_file_path):
        """
        Restaura toda la base de datos desde un archivo de backup
        
        Args:
            backup_file_path: Ruta al archivo de backup (.sqlite3 o .sql)
        """
        try:
            import shutil
            from django.core.management import call_command
            
            db_engine = settings.DATABASES['default']['ENGINE']
            
            if 'sqlite' in db_engine:
                # Para SQLite, reemplazar el archivo de base de datos
                current_db_path = settings.DATABASES['default']['NAME']
                
                # Crear backup del archivo actual antes de reemplazar
                backup_current = f"{current_db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                try:
                    # Hacer backup del archivo actual
                    if os.path.exists(current_db_path):
                        shutil.copy2(current_db_path, backup_current)
                    
                    # Reemplazar con el nuevo archivo
                    shutil.copy2(backup_file_path, current_db_path)
                    
                    # Verificar que la base de datos es válida
                    call_command('check', '--database', 'default')
                    
                    return {
                        'success': True,
                        'message': 'Base de datos restaurada exitosamente',
                        'backup_of_current': backup_current
                    }
                    
                except Exception as e:
                    # Si falla, restaurar el backup anterior
                    if os.path.exists(backup_current):
                        shutil.copy2(backup_current, current_db_path)
                    raise e
                    
            elif 'postgresql' in db_engine:
                # Para PostgreSQL, usar comando de gestión
                from django.core.management import call_command
                from io import StringIO
                
                try:
                    out = StringIO()
                    call_command('restore_database', '--file', backup_file_path, '--no-backup', stdout=out)
                    
                    return {
                        'success': True,
                        'type': 'postgresql',
                        'message': 'Base de datos PostgreSQL restaurada exitosamente'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Error al restaurar PostgreSQL: {str(e)}'
                    }
            
            else:
                return {
                    'success': False,
                    'error': 'Tipo de base de datos no soportado'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def restore_parking_lot_data(backup_data, overwrite=False):
        """
        Restaura los datos de un parqueadero desde un backup
        
        Args:
            backup_data: Diccionario con los datos del backup
            overwrite: Si True, sobrescribe datos existentes
        """
        try:
            from django.core import serializers
            from django.db import transaction
            
            with transaction.atomic():
                # Verificar metadata
                if 'metadata' not in backup_data:
                    return {
                        'success': False,
                        'error': 'Formato de backup inválido'
                    }
                
                metadata = backup_data['metadata']
                parking_lot_id = metadata.get('parking_lot_id')
                
                # Verificar si el parqueadero existe
                parking_exists = ParkingLot.objects.filter(id=parking_lot_id).exists()
                
                if parking_exists and not overwrite:
                    return {
                        'success': False,
                        'error': 'El parqueadero ya existe. Use overwrite=True para sobrescribir.'
                    }
                
                # Restaurar datos
                restored_counts = {}
                
                # Restaurar parqueadero
                if overwrite and parking_exists:
                    ParkingLot.objects.filter(id=parking_lot_id).delete()
                
                for obj in serializers.deserialize('json', json.dumps([backup_data['parking_lot']])):
                    obj.save()
                restored_counts['parking_lot'] = 1
                
                # Restaurar categorías
                if overwrite:
                    VehicleCategory.objects.filter(parking_lot_id=parking_lot_id).delete()
                for obj in serializers.deserialize('json', json.dumps(backup_data['categories'])):
                    obj.save()
                restored_counts['categories'] = len(backup_data['categories'])
                
                # Restaurar tickets
                if overwrite:
                    ParkingTicket.objects.filter(parking_lot_id=parking_lot_id).delete()
                for obj in serializers.deserialize('json', json.dumps(backup_data['tickets'])):
                    obj.save()
                restored_counts['tickets'] = len(backup_data['tickets'])
                
                # Restaurar clientes
                if overwrite:
                    Cliente.objects.filter(parking_lot_id=parking_lot_id).delete()
                for obj in serializers.deserialize('json', json.dumps(backup_data['clientes'])):
                    obj.save()
                restored_counts['clientes'] = len(backup_data['clientes'])
                
                # Restaurar mensualidades
                if overwrite:
                    Mensualidad.objects.filter(parking_lot_id=parking_lot_id).delete()
                for obj in serializers.deserialize('json', json.dumps(backup_data['mensualidades'])):
                    obj.save()
                restored_counts['mensualidades'] = len(backup_data['mensualidades'])
                
                # Restaurar métodos de pago
                if overwrite:
                    PaymentMethod.objects.filter(parking_lot_id=parking_lot_id).delete()
                for obj in serializers.deserialize('json', json.dumps(backup_data['payment_methods'])):
                    obj.save()
                restored_counts['payment_methods'] = len(backup_data['payment_methods'])
                
                return {
                    'success': True,
                    'restored_counts': restored_counts,
                    'parking_lot_name': metadata.get('parking_lot_name')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
