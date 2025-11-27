# -*- coding: utf-8 -*-
"""
Utilidades comunes para el sistema de parqueadero
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def require_parking_lot(view_func):
    """
    Decorador que verifica que el usuario tenga un parqueadero asignado
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.current_parking_lot:
            messages.error(request, 'No tienes un parqueadero asignado.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_active_subscription(view_func):
    """
    Decorador que verifica que la suscripción esté activa
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.current_parking_lot:
            messages.error(request, 'No tienes un parqueadero asignado.')
            return redirect('login')
        
        parking_lot = request.current_parking_lot
        if not parking_lot.is_active or parking_lot.is_expired():
            messages.error(request, 'Tu suscripción ha expirado. Contacta al administrador.')
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def validate_parking_lot_ownership(user, obj):
    """
    Valida que un objeto pertenezca al parqueadero del usuario
    Lanza PermissionDenied si no tiene acceso
    """
    if user.is_superuser:
        return True
    
    if not hasattr(obj, 'parking_lot'):
        raise PermissionDenied("El objeto no tiene parqueadero asociado")
    
    # Obtener el parqueadero del usuario
    user_parking_lot = None
    if hasattr(user, 'parking_lot'):
        user_parking_lot = user.parking_lot
    else:
        from .models import UserParkingLot
        assignment = UserParkingLot.objects.filter(user=user).first()
        if assignment:
            user_parking_lot = assignment.parking_lot
    
    if not user_parking_lot or obj.parking_lot != user_parking_lot:
        raise PermissionDenied("No tienes permiso para acceder a este recurso")
    
    return True


def format_currency(amount):
    """
    Formatea un monto como moneda colombiana
    """
    try:
        amount = float(amount)
        return f"${amount:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return "$0"


def format_duration(hours, minutes=0):
    """
    Formatea una duración en formato legible
    """
    if hours == 0 and minutes == 0:
        return "0 minutos"
    
    parts = []
    if hours > 0:
        parts.append(f"{int(hours)} hora{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{int(minutes)} minuto{'s' if minutes != 1 else ''}")
    
    return " y ".join(parts)


def sanitize_plate(plate):
    """
    Sanitiza una placa vehicular o código de barras
    Permite alfanuméricos y guiones para códigos de barras
    """
    if not plate:
        return ""
    
    # Convertir a mayúsculas y eliminar espacios al inicio/final
    plate = str(plate).upper().strip()
    
    # Permitir alfanuméricos y guiones (para códigos de barras)
    plate = ''.join(c for c in plate if c.isalnum() or c == '-')
    
    return plate


def validate_nit(nit):
    """
    Valida un NIT colombiano (básico)
    """
    if not nit:
        return False
    
    # Eliminar caracteres no numéricos excepto el guión
    nit = ''.join(c for c in nit if c.isdigit() or c == '-')
    
    # Debe tener al menos 9 dígitos
    digits = ''.join(c for c in nit if c.isdigit())
    return len(digits) >= 9


def get_client_ip(request):
    """
    Obtiene la IP del cliente desde el request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_user_action(user, action, details=None):
    """
    Registra una acción del usuario (para auditoría futura)
    """
    # TODO: Implementar sistema de auditoría
    pass
