# -*- coding: utf-8 -*-
"""
Backend de autenticación personalizado para permitir login con email
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class EmailBackend(ModelBackend):
    """
    Permite autenticación con email o username
    Incluye protección contra fuerza bruta
    """
    
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 300  # 5 minutos en segundos
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        
        # Verificar intentos fallidos (protección contra fuerza bruta)
        if request:
            ip_address = self._get_client_ip(request)
            lockout_key = f'auth_lockout_{ip_address}_{username}'
            attempts_key = f'auth_attempts_{ip_address}_{username}'
            
            # Verificar si está bloqueado
            if cache.get(lockout_key):
                logger.warning(f'Intento de login bloqueado para {username} desde {ip_address}')
                return None
            
            # Obtener número de intentos
            attempts = cache.get(attempts_key, 0)
            
            if attempts >= self.MAX_ATTEMPTS:
                # Bloquear por LOCKOUT_DURATION segundos
                cache.set(lockout_key, True, self.LOCKOUT_DURATION)
                cache.delete(attempts_key)
                logger.warning(f'Usuario {username} bloqueado por múltiples intentos fallidos desde {ip_address}')
                return None
        
        user = None
        
        # Intentar buscar por username primero (más específico)
        try:
            user = User.objects.select_related('parking_lot').get(username=username)
        except User.DoesNotExist:
            # Si no funciona por username, intentar por email
            try:
                user = User.objects.select_related('parking_lot').filter(email=username).first()
            except User.DoesNotExist:
                pass
        
        # Verificar contraseña
        if user and user.check_password(password) and self.user_can_authenticate(user):
            # Login exitoso - limpiar intentos
            if request:
                cache.delete(attempts_key)
                cache.delete(lockout_key)
            
            logger.info(f'Login exitoso para {username}')
            return user
        
        # Login fallido - incrementar intentos
        if request:
            attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, attempts, self.LOCKOUT_DURATION)
            logger.warning(f'Intento de login fallido para {username} desde {ip_address} (intento {attempts})')
        
        return None
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
