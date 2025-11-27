from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.core.cache import cache
from .models import ParkingLot


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware para establecer el parqueadero (tenant) actual basado en el usuario autenticado
    y verificar el estado de la suscripción con caché para mejor rendimiento
    """
    
    # Rutas que no requieren verificación de suscripción
    EXEMPT_PATHS = (
        '/accounts/login/',
        '/accounts/logout/',
        '/superadmin/',
        '/admin/',
        '/static/',
        '/media/',
    )
    
    def process_request(self, request):
        request.current_parking_lot = None
        
        # Verificar si la ruta actual está exenta
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            return None
        
        if not request.user.is_authenticated:
            return None
            
        # Si es superusuario, no tiene parqueadero asignado
        if request.user.is_superuser:
            return None
        
        # Intentar obtener del caché primero (válido por 5 minutos)
        cache_key = f'parking_lot_user_{request.user.id}'
        parking_lot = cache.get(cache_key)
        
        if parking_lot is None:
            # Primero intentar obtener el parqueadero del usuario dueño (OneToOne)
            try:
                parking_lot = ParkingLot.objects.select_related('subscription_plan').get(user=request.user)
            except ParkingLot.DoesNotExist:
                # Si no es dueño, buscar en las asignaciones (cajeros, operadores)
                from .models import UserParkingLot
                assignment = UserParkingLot.objects.select_related('parking_lot__subscription_plan').filter(user=request.user).first()
                parking_lot = assignment.parking_lot if assignment else None
            
            # Guardar en caché por 5 minutos
            if parking_lot:
                cache.set(cache_key, parking_lot, 300)
        
        if parking_lot:
            request.current_parking_lot = parking_lot
            
            # Verificar si la suscripción está activa
            if not parking_lot.is_active or parking_lot.is_expired():
                messages.error(request, 'Tu suscripción ha expirado. Contacta al administrador para renovarla.')
                return redirect('login')
        
        return None
