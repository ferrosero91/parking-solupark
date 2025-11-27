# -*- coding: utf-8 -*-
"""
Servicios de negocio para el sistema de parqueadero
Separación de lógica de negocio de las vistas (bajo acoplamiento, alta cohesión)
"""

from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, datetime
from decimal import Decimal
from .models import ParkingTicket, Mensualidad, Caja, PaymentMethod


class ReportService:
    """Servicio para generación de reportes y estadísticas"""
    
    @staticmethod
    def get_date_range(filter_type, start_date_str=None, end_date_str=None):
        """
        Calcula el rango de fechas según el tipo de filtro
        Retorna: (start_date, end_date)
        """
        today = timezone.now()
        
        if filter_type == 'today':
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'yesterday':
            yesterday = today - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'week':
            start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'month':
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'year':
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif filter_type == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(f"{start_date_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
                start_date = timezone.make_aware(start_date)
                end_date = datetime.strptime(f"{end_date_str} 23:59:59", '%Y-%m-%d %H:%M:%S')
                end_date = timezone.make_aware(end_date)
            except ValueError:
                start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    
    @staticmethod
    def get_revenue_summary(parking_lot, start_date, end_date):
        """
        Obtiene el resumen de ingresos para un período
        Retorna: dict con totales de tickets y mensualidades
        """
        cache_key = f'revenue_summary_{parking_lot.id}_{start_date.date()}_{end_date.date()}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Ingresos de tickets
        tickets_revenue = ParkingTicket.objects.filter(
            parking_lot=parking_lot,
            exit_time__range=(start_date, end_date),
            exit_time__isnull=False,
            amount_paid__isnull=False
        ).aggregate(
            total=Sum('amount_paid'),
            count=Count('id')
        )
        
        # Ingresos de mensualidades
        mensualidades_revenue = Mensualidad.objects.filter(
            parking_lot=parking_lot,
            fecha_pago__range=(start_date, end_date),
            estado='PAGADO'
        ).aggregate(
            total=Sum('monto'),
            count=Count('id')
        )
        
        summary = {
            'tickets_total': tickets_revenue['total'] or 0,
            'tickets_count': tickets_revenue['count'] or 0,
            'mensualidades_total': mensualidades_revenue['total'] or 0,
            'mensualidades_count': mensualidades_revenue['count'] or 0,
            'total': (tickets_revenue['total'] or 0) + (mensualidades_revenue['total'] or 0)
        }
        
        # Cachear por 5 minutos
        cache.set(cache_key, summary, 300)
        return summary
    
    @staticmethod
    def get_payment_method_summary(parking_lot, start_date, end_date):
        """
        Obtiene el resumen por medio de pago
        Retorna: lista de diccionarios con totales por medio de pago
        """
        # Tickets por medio de pago
        tickets_summary = ParkingTicket.objects.filter(
            parking_lot=parking_lot,
            exit_time__range=(start_date, end_date),
            exit_time__isnull=False,
            amount_paid__isnull=False
        ).values('payment_method__nombre', 'payment_method__icono').annotate(
            total=Sum('amount_paid'),
            count=Count('id')
        )
        
        # Mensualidades por medio de pago
        mensualidades_summary = Mensualidad.objects.filter(
            parking_lot=parking_lot,
            fecha_pago__range=(start_date, end_date),
            estado='PAGADO'
        ).values('payment_method__nombre', 'payment_method__icono').annotate(
            total=Sum('monto'),
            count=Count('id')
        )
        
        # Combinar ambos resúmenes
        payment_dict = {}
        
        for item in tickets_summary:
            nombre = item['payment_method__nombre'] or 'Sin especificar'
            payment_dict[nombre] = {
                'nombre': nombre,
                'icono': item['payment_method__icono'],
                'total': item['total'] or 0,
                'count': item['count'] or 0,
                'tickets_count': item['count'] or 0,
                'mensualidades_count': 0
            }
        
        for item in mensualidades_summary:
            nombre = item['payment_method__nombre'] or 'Sin especificar'
            if nombre in payment_dict:
                payment_dict[nombre]['total'] += item['total'] or 0
                payment_dict[nombre]['count'] += item['count'] or 0
                payment_dict[nombre]['mensualidades_count'] = item['count'] or 0
            else:
                payment_dict[nombre] = {
                    'nombre': nombre,
                    'icono': item['payment_method__icono'],
                    'total': item['total'] or 0,
                    'count': item['count'] or 0,
                    'tickets_count': 0,
                    'mensualidades_count': item['count'] or 0
                }
        
        return sorted(payment_dict.values(), key=lambda x: x['total'], reverse=True)


class TicketService:
    """Servicio para operaciones con tickets"""
    
    @staticmethod
    def calculate_fee(ticket):
        """
        Calcula la tarifa de un ticket
        Retorna: Decimal con el monto a pagar
        """
        if ticket.exit_time:
            duration = ticket.exit_time - ticket.entry_time
        else:
            duration = timezone.now() - ticket.entry_time
        
        hours = duration.total_seconds() / 3600
        
        # Verificar si es mensualidad
        if ticket.category.is_monthly and ticket.monthly_expiry:
            check_time = ticket.exit_time if ticket.exit_time else timezone.now()
            if check_time <= ticket.monthly_expiry:
                return Decimal(str(ticket.category.monthly_rate))
        
        # Cálculo por horas
        total = Decimal(str(ticket.category.first_hour_rate))
        if hours > 1:
            import math
            additional_hours = math.ceil(hours - 1)
            total += Decimal(str(additional_hours)) * Decimal(str(ticket.category.additional_hour_rate))
        
        return round(total, 2)
    
    @staticmethod
    def register_exit(ticket, payment_method_id=None):
        """
        Registra la salida de un vehículo
        Retorna: ticket actualizado
        """
        ticket.exit_time = timezone.now()
        ticket.amount_paid = TicketService.calculate_fee(ticket)
        
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id,
                    parking_lot=ticket.parking_lot
                )
                ticket.payment_method = payment_method
            except PaymentMethod.DoesNotExist:
                pass
        
        ticket.save()
        
        # Invalidar caché de reportes (solo las claves específicas)
        today = timezone.now().date()
        cache_keys = [
            f'revenue_summary_{ticket.parking_lot.id}_{today}',
            f'dashboard_stats_{ticket.parking_lot.id}_{today}',
        ]
        for key in cache_keys:
            cache.delete(key)
        
        return ticket


class CashRegisterService:
    """Servicio para operaciones de caja"""
    
    @staticmethod
    def get_or_create_caja(parking_lot, date):
        """
        Obtiene o crea el registro de caja para una fecha
        Retorna: instancia de Caja
        """
        caja, created = Caja.objects.get_or_create(
            parking_lot=parking_lot,
            fecha=date,
            tipo='Ingreso',
            defaults={
                'monto': Decimal('0.00'),
                'dinero_inicial': Decimal('0.00'),
                'descripcion': f'Ingresos del {date}'
            }
        )
        return caja
    
    @staticmethod
    def calculate_cash_total(parking_lot, start_date, end_date):
        """
        Calcula el total en efectivo para un período
        Retorna: Decimal con el total
        """
        efectivo_method = PaymentMethod.objects.filter(
            parking_lot=parking_lot,
            nombre__iexact='efectivo'
        ).first()
        
        if not efectivo_method:
            return Decimal('0.00')
        
        # Tickets en efectivo
        tickets_total = ParkingTicket.objects.filter(
            parking_lot=parking_lot,
            exit_time__gte=start_date,
            exit_time__lt=end_date,
            exit_time__isnull=False,
            amount_paid__isnull=False,
            payment_method=efectivo_method
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Mensualidades en efectivo
        mensualidades_total = Mensualidad.objects.filter(
            parking_lot=parking_lot,
            fecha_pago__gte=start_date,
            fecha_pago__lt=end_date,
            estado='PAGADO',
            payment_method=efectivo_method
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        
        return tickets_total + mensualidades_total
    
    @staticmethod
    def realizar_cuadre(caja, dinero_final):
        """
        Realiza el cuadre de caja
        Retorna: dict con resultado del cuadre
        """
        if caja.cuadre_realizado:
            return {
                'success': False,
                'message': 'El cuadre ya fue realizado'
            }
        
        caja.dinero_final = Decimal(str(dinero_final))
        caja.cuadre_realizado = True
        caja.save()
        
        diferencia = (caja.dinero_final - caja.dinero_inicial) - caja.monto
        
        return {
            'success': True,
            'diferencia': diferencia,
            'diferencia_abs': abs(diferencia)
        }


class SecurityService:
    """Servicio para validaciones de seguridad"""
    
    @staticmethod
    def validate_parking_lot_access(user, parking_lot):
        """
        Valida que un usuario tenga acceso a un parqueadero
        Retorna: bool
        """
        if user.is_superuser:
            return True
        
        # Verificar si es el dueño
        if hasattr(user, 'parking_lot') and user.parking_lot == parking_lot:
            return True
        
        # Verificar si tiene asignación
        from .models import UserParkingLot
        return UserParkingLot.objects.filter(
            user=user,
            parking_lot=parking_lot
        ).exists()
    
    @staticmethod
    def validate_subscription(parking_lot):
        """
        Valida que la suscripción esté activa
        Retorna: dict con estado y mensaje
        """
        if not parking_lot.is_active:
            return {
                'valid': False,
                'message': 'El parqueadero está inactivo'
            }
        
        if parking_lot.is_expired():
            return {
                'valid': False,
                'message': 'La suscripción ha expirado'
            }
        
        days_remaining = parking_lot.days_until_expiration()
        if days_remaining <= 5:
            return {
                'valid': True,
                'warning': True,
                'message': f'La suscripción vence en {days_remaining} días',
                'days_remaining': days_remaining
            }
        
        return {
            'valid': True,
            'warning': False
        }
