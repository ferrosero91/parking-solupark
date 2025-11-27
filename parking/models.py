from django.db import models
from django.contrib.auth.models import User
import uuid
import math
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from django.core.files import File
import barcode
from barcode.writer import ImageWriter
import base64
from barcode import Code128


# Modelo para planes de suscripción
class SubscriptionPlan(models.Model):
    PLAN_TYPE_CHOICES = [
        ('MENSUAL', 'Mensual'),
        ('TRIMESTRAL', 'Trimestral'),
        ('SEMESTRAL', 'Semestral'),
        ('ANUAL', 'Anual'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Nombre del Plan')
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, unique=True, verbose_name='Tipo de Plan')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio')
    duration_days = models.IntegerField(verbose_name='Duración en Días')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - ${self.price}"
    
    class Meta:
        verbose_name = "Plan de Suscripción"
        verbose_name_plural = "Planes de Suscripción"
        ordering = ['duration_days']


# Modelo para representar cada parqueadero (tenant)
class ParkingLot(models.Model):
    PLAN_CHOICES = [
        ('MENSUAL', 'Mensual'),
        ('ANUAL', 'Anual'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parking_lot')
    empresa = models.CharField(max_length=255, verbose_name='Nombre del Parqueadero')
    nit = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Campos de suscripción
    plan_type = models.CharField(max_length=10, choices=PLAN_CHOICES, default='MENSUAL', verbose_name='Tipo de Plan')
    subscription_plan = models.ForeignKey('SubscriptionPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='parking_lots', verbose_name='Plan de Suscripción')
    subscription_start = models.DateField(null=True, blank=True, verbose_name='Inicio de Suscripción')
    subscription_end = models.DateField(null=True, blank=True, verbose_name='Fin de Suscripción')
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Precio Mensual')
    annual_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Precio Anual')
    last_payment_date = models.DateField(null=True, blank=True, verbose_name='Última Fecha de Pago')
    payment_status = models.CharField(max_length=20, default='PENDIENTE', verbose_name='Estado de Pago',
                                     choices=[
                                         ('PAGADO', 'Pagado'),
                                         ('PENDIENTE', 'Pendiente'),
                                         ('VENCIDO', 'Vencido'),
                                     ])

    def __str__(self):
        return self.empresa
    
    def get_current_price(self):
        """Obtiene el precio correcto según el plan actual"""
        if self.subscription_plan:
            return self.subscription_plan.price
        
        # Fallback a los precios antiguos
        if self.plan_type == 'ANUAL':
            return self.annual_price if self.annual_price > 0 else self.monthly_price * 12
        return self.monthly_price
    
    def is_subscription_active(self):
        """Verifica si la suscripción está activa"""
        if not self.subscription_end:
            return False
        return timezone.now().date() <= self.subscription_end
    
    def days_until_expiration(self):
        """Calcula los días restantes de la suscripción (puede ser negativo si ya venció)"""
        if not self.subscription_end:
            return 0
        delta = self.subscription_end - timezone.now().date()
        return delta.days
    
    def is_expired(self):
        """Verifica si la suscripción está vencida"""
        if not self.subscription_end:
            return True
        return timezone.now().date() > self.subscription_end

    class Meta:
        verbose_name = "Parqueadero"
        verbose_name_plural = "Parqueaderos"
        indexes = [
            models.Index(fields=['subscription_end', 'is_active']),
            models.Index(fields=['payment_status']),
        ]


# Categorías de vehículos por parqueadero
class VehicleCategory(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    first_hour_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    additional_hour_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_monthly = models.BooleanField(default=False)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.parking_lot.empresa} - {self.name}"

    class Meta:
        verbose_name_plural = "Vehicle Categories"
        unique_together = ['parking_lot', 'name']
        indexes = [
            models.Index(fields=['parking_lot', 'is_monthly']),
        ]

# ParkingTicket con mejoras y multitenant
class ParkingTicket(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='tickets')
    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False)
    category = models.ForeignKey('VehicleCategory', on_delete=models.CASCADE)
    cliente = models.ForeignKey('Cliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    placa = models.CharField(max_length=20)
    color = models.CharField(max_length=50)
    marca = models.CharField(max_length=50)
    cascos = models.IntegerField(null=True, blank=True)
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Medio de Pago')
    barcode = models.ImageField(upload_to='barcodes/', blank=True)
    monthly_expiry = models.DateTimeField(null=True, blank=True)
    es_mensualidad = models.BooleanField(default=False, verbose_name='Es Mensualidad')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parking_lot', 'placa'],
                condition=models.Q(exit_time__isnull=True),
                name='unique_active_plate_per_parking'
            )
        ]
        indexes = [
            models.Index(fields=['parking_lot', 'exit_time']),
            models.Index(fields=['parking_lot', 'placa', 'exit_time']),
            models.Index(fields=['entry_time']),
            models.Index(fields=['payment_method']),
        ]

    def __str__(self):
        return f"{self.placa} - {self.entry_time.strftime('%Y-%m-%d %H:%M')}"
    
    def get_barcode_base64(self):
        buffer = BytesIO()
        code = Code128(self.placa, writer=ImageWriter())
        code.write(buffer)
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{base64_data}'

    def save(self, *args, **kwargs):
        # Generar el código de barras con la placa si no existe
        if not self.barcode:
            code = barcode.Code128(self.placa, writer=ImageWriter())  # Usar la placa en lugar de ticket_id
            buffer = BytesIO()
            code.write(buffer)
            self.barcode.save(
                f'barcode_{self.placa}.png',  # Nombrar el archivo con la placa
                File(buffer),
                save=False
            )
        # Asegurarse de que entry_time tenga un valor antes de calcular monthly_expiry
        if not self.entry_time:
            self.entry_time = timezone.now()
        # Si es categoría mensual y no tiene fecha de vencimiento, asignar un mes desde la entrada
        if self.category.is_monthly and not self.monthly_expiry:
            self.monthly_expiry = self.entry_time + timedelta(days=30)
        super().save(*args, **kwargs)

    """
    def generate_barcode_image(self):
        buffer = BytesIO()
        code = Code128(self.placa, writer=ImageWriter())
        code.write(buffer)
        buffer.seek(0)
        return ContentFile(buffer.read(), name=f'barcode_{self.placa}.png')
    """
    

    def calculate_fee(self):
        if self.exit_time:
            if self.category.is_monthly and self.monthly_expiry and self.exit_time <= self.monthly_expiry:
                return float(self.category.monthly_rate)
            duration = self.exit_time - self.entry_time
            hours = duration.total_seconds() / 3600

            total = float(self.category.first_hour_rate)
            if hours > 1:
                additional_hours = math.ceil(hours - 1)
                total += additional_hours * float(self.category.additional_hour_rate)

            return round(total, 2)
        return self.calculate_current_fee()

    def calculate_current_fee(self):
        if not self.exit_time:
            if self.category.is_monthly and self.monthly_expiry and timezone.now() <= self.monthly_expiry:
                return float(self.category.monthly_rate)
            duration = timezone.now() - self.entry_time
            hours = duration.total_seconds() / 3600

            total = float(self.category.first_hour_rate)
            if hours > 1:
                additional_hours = math.ceil(hours - 1)
                total += additional_hours * float(self.category.additional_hour_rate)

            return round(total, 2)
        return 0

    def get_duration(self):
        if self.exit_time:
            duration = self.exit_time - self.entry_time
            return math.ceil(duration.total_seconds() / 3600)
        return self.get_current_duration()['hours']

    def get_current_duration(self):
        if not self.exit_time:
            duration = timezone.now() - self.entry_time
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            return {'hours': int(hours), 'minutes': int(minutes)}
        return {'hours': 0, 'minutes': 0}

    def get_status(self):
        if not self.exit_time:
            duration = self.get_current_duration()
            current_fee = self.calculate_current_fee()
            monthly_status = None
            if self.category.is_monthly:
                monthly_status = 'Vigente' if timezone.now() <= self.monthly_expiry else 'Vencido'
            return {
                'duration': duration,
                'current_fee': current_fee,
                'is_active': True,
                'monthly_status': monthly_status
            }
        return {
            'duration': {'hours': 0, 'minutes': 0},
            'current_fee': self.amount_paid or 0,
            'is_active': False,
            'monthly_status': None
        }

# Al final del archivo, añade el modelo Caja si no está


class Caja(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='cajas')
    fecha = models.DateField(default=timezone.now)
    tipo = models.CharField(max_length=50, choices=[('Ingreso', 'Ingreso'), ('Egreso', 'Egreso')])
    monto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descripcion = models.TextField(blank=True)
    dinero_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    dinero_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cuadre_realizado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('parking_lot', 'fecha', 'tipo')
        indexes = [
            models.Index(fields=['parking_lot', 'fecha']),
        ]

    def __str__(self):
        return f"{self.parking_lot.empresa} - {self.fecha} - {self.tipo} - ${self.monto}"


# Modelo de Cliente para mensualidades
class Cliente(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='clientes')
    nombre = models.CharField(max_length=200, verbose_name='Nombre Completo')
    documento = models.CharField(max_length=20, verbose_name='Documento de Identidad')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    placa = models.CharField(max_length=20, verbose_name='Placa del Vehículo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        unique_together = ['parking_lot', 'documento']
        indexes = [
            models.Index(fields=['parking_lot', 'is_active']),
            models.Index(fields=['documento']),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.placa}"

    def get_mensualidad_activa(self):
        """Retorna la mensualidad activa del cliente si existe"""
        return self.mensualidades.filter(
            fecha_vencimiento__gte=timezone.now(),
            estado__in=['PAGADO', 'PENDIENTE']
        ).first()

    def tiene_mensualidad_vigente(self):
        """Verifica si el cliente tiene una mensualidad vigente"""
        mensualidad = self.get_mensualidad_activa()
        return mensualidad is not None and mensualidad.estado == 'PAGADO'


# Modelo de Medio de Pago
class PaymentMethod(models.Model):
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='payment_methods')
    nombre = models.CharField(max_length=100, verbose_name='Nombre del Medio de Pago')
    descripcion = models.TextField(blank=True, null=True, verbose_name='Descripción')
    icono = models.CharField(max_length=50, default='fa-money-bill-wave', verbose_name='Icono FontAwesome')
    color = models.CharField(max_length=20, default='primary', verbose_name='Color', 
                            choices=[
                                ('primary', 'Azul'),
                                ('success', 'Verde'),
                                ('warning', 'Naranja'),
                                ('danger', 'Rojo'),
                                ('info', 'Cyan'),
                                ('purple', 'Morado'),
                            ])
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.IntegerField(default=0, verbose_name='Orden de visualización')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Medio de Pago"
        verbose_name_plural = "Medios de Pago"
        ordering = ['orden', 'nombre']
        unique_together = ['parking_lot', 'nombre']

    def __str__(self):
        return self.nombre


# Modelo de Mensualidad
class UserParkingLot(models.Model):
    """
    Modelo para asociar usuarios secundarios (cajeros, operadores) a parqueaderos
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parking_lot_assignments')
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='user_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Asignación Usuario-Parqueadero'
        verbose_name_plural = 'Asignaciones Usuario-Parqueadero'
        unique_together = ('user', 'parking_lot')
    
    def __str__(self):
        return f'{self.user.username} - {self.parking_lot.empresa}'


class Mensualidad(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('PAGADO', 'Pagado'),
        ('VENCIDO', 'Vencido'),
        ('CANCELADO', 'Cancelado'),
    ]

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='mensualidades')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='mensualidades')
    category = models.ForeignKey(VehicleCategory, on_delete=models.CASCADE, verbose_name='Categoría')
    ticket = models.ForeignKey(ParkingTicket, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensualidad')
    
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de Vencimiento')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    fecha_pago = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Pago')
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Medio de Pago')
    metodo_pago = models.CharField(max_length=50, blank=True, null=True, verbose_name='Método de Pago (Legacy)')
    observaciones = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mensualidad"
        verbose_name_plural = "Mensualidades"
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['parking_lot', 'estado', 'fecha_vencimiento']),
            models.Index(fields=['cliente', 'estado']),
            models.Index(fields=['fecha_pago']),
        ]

    def __str__(self):
        return f"{self.cliente.nombre} - {self.fecha_inicio} a {self.fecha_vencimiento}"

    def esta_vigente(self):
        """Verifica si la mensualidad está vigente"""
        return (
            self.estado == 'PAGADO' and
            self.fecha_vencimiento >= timezone.now().date()
        )

    def dias_restantes(self):
        """Calcula los días restantes de la mensualidad"""
        if self.fecha_vencimiento >= timezone.now().date():
            delta = self.fecha_vencimiento - timezone.now().date()
            return delta.days
        return 0

    def marcar_como_pagado(self):
        """Marca la mensualidad como pagada"""
        self.estado = 'PAGADO'
        self.fecha_pago = timezone.now()
        self.save()

    def verificar_vencimiento(self):
        """Verifica y actualiza el estado si está vencida"""
        if self.fecha_vencimiento < timezone.now().date() and self.estado == 'PENDIENTE':
            self.estado = 'VENCIDO'
            self.save()


# Modelo para registrar pagos de suscripción de parqueaderos
class SubscriptionPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('TARJETA', 'Tarjeta de Crédito/Débito'),
        ('NEQUI', 'Nequi'),
        ('DAVIPLATA', 'Daviplata'),
        ('OTRO', 'Otro'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]
    
    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='subscription_payments', verbose_name='Parqueadero')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name='Método de Pago')
    payment_date = models.DateTimeField(default=timezone.now, verbose_name='Fecha de Pago')
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='Número de Referencia')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='APROBADO', verbose_name='Estado')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_payments', verbose_name='Procesado por')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Información de la suscripción al momento del pago
    subscription_start = models.DateField(verbose_name='Inicio de Suscripción')
    subscription_end = models.DateField(verbose_name='Fin de Suscripción')
    plan_type = models.CharField(max_length=10, verbose_name='Tipo de Plan')
    
    def __str__(self):
        return f"{self.parking_lot.empresa} - ${self.amount} - {self.payment_date.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Pago de Suscripción"
        verbose_name_plural = "Pagos de Suscripción"
        ordering = ['-payment_date']
