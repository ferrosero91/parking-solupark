from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db import models
from django.utils import timezone
from datetime import timedelta
from .models import ParkingLot, VehicleCategory
from .forms import ParkingLotCreateForm, ParkingLotEditForm


def is_superuser(user):
    return user.is_superuser


def superuser_required(view_func):
    """Decorador personalizado para requerir superusuario"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('superadmin_login')
        if not request.user.is_superuser:
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('superadmin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_login(request):
    """Login específico para superadministradores"""
    # Limpiar mensajes antiguos al acceder al login
    storage = messages.get_messages(request)
    storage.used = True
    
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('superadmin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_superuser:
            login(request, user)
            messages.success(request, f'Bienvenido, {user.username}!')
            return redirect('superadmin_dashboard')
        else:
            context = {
                'error': 'Credenciales inválidas o no tienes permisos de superadministrador.'
            }
            return render(request, 'parking/superadmin/login.html', context)
    
    return render(request, 'parking/superadmin/login.html')


@superuser_required
def superadmin_dashboard(request):
    """Dashboard del superadministrador"""
    parking_lots = ParkingLot.objects.all().select_related('user')
    
    context = {
        'parking_lots': parking_lots,
        'total_parking_lots': parking_lots.count(),
        'active_parking_lots': parking_lots.filter(is_active=True).count(),
    }
    return render(request, 'parking/superadmin/dashboard.html', context)


@superuser_required
def create_parking_lot(request):
    """Crear un nuevo parqueadero"""
    if request.method == 'POST':
        form = ParkingLotCreateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Crear usuario
                    user = User.objects.create_user(
                        username=form.cleaned_data['email'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['empresa']
                    )
                    
                    # Obtener el plan de suscripción seleccionado
                    subscription_plan = form.cleaned_data['subscription_plan']
                    subscription_start = form.cleaned_data.get('subscription_start') or timezone.now().date()
                    subscription_end = subscription_start + timedelta(days=subscription_plan.duration_days)
                    
                    # Crear parqueadero
                    parking_lot = ParkingLot.objects.create(
                        user=user,
                        empresa=form.cleaned_data['empresa'],
                        nit=form.cleaned_data.get('nit', ''),
                        telefono=form.cleaned_data['telefono'],
                        direccion=form.cleaned_data['direccion'],
                        is_active=True,
                        plan_type=subscription_plan.plan_type,
                        subscription_plan=subscription_plan,
                        monthly_price=subscription_plan.price if subscription_plan.plan_type == 'MENSUAL' else 0,
                        annual_price=subscription_plan.price if subscription_plan.plan_type == 'ANUAL' else 0,
                        subscription_start=subscription_start,
                        subscription_end=subscription_end,
                        payment_status='PAGADO',
                        last_payment_date=subscription_start
                    )
                    
                    # Asignar al grupo Admin con permisos completos
                    from django.contrib.auth.models import Permission
                    admin_group, created = Group.objects.get_or_create(name='Admin')
                    
                    # Si el grupo es nuevo, asignar todos los permisos
                    if created:
                        permissions = Permission.objects.filter(
                            content_type__app_label='parking'
                        )
                        admin_group.permissions.set(permissions)
                    
                    user.groups.add(admin_group)
                    user.is_staff = True
                    user.save()
                    
                    # Asignar el usuario al parqueadero
                    from .models import UserParkingLot
                    UserParkingLot.objects.create(
                        user=user,
                        parking_lot=parking_lot
                    )
                    
                    # Crear categorías por defecto
                    default_categories = [
                        {'name': 'MOTOS', 'first_hour_rate': 2000, 'additional_hour_rate': 1000},
                        {'name': 'CARROS', 'first_hour_rate': 3000, 'additional_hour_rate': 2000},
                        {'name': 'CAMIONETAS', 'first_hour_rate': 4000, 'additional_hour_rate': 2500},
                    ]
                    
                    for cat_data in default_categories:
                        VehicleCategory.objects.create(
                            parking_lot=parking_lot,
                            **cat_data
                        )
                    
                    messages.success(request, f'Parqueadero "{parking_lot.empresa}" creado exitosamente.')
                    return redirect('superadmin_dashboard')
            except Exception as e:
                messages.error(request, f'Error al crear el parqueadero: {str(e)}')
    else:
        form = ParkingLotCreateForm()
    
    return render(request, 'parking/superadmin/create_parking_lot.html', {'form': form})


@superuser_required
def edit_parking_lot(request, pk):
    """Editar un parqueadero existente"""
    # SEGURIDAD: Solo superusuarios pueden editar cualquier parqueadero
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    
    if request.method == 'POST':
        form = ParkingLotEditForm(request.POST, instance=parking_lot)
        if form.is_valid():
            parking_lot = form.save(commit=False)
            
            # Si se seleccionó un plan, sincronizar el plan_type
            if parking_lot.subscription_plan:
                parking_lot.plan_type = parking_lot.subscription_plan.plan_type
                # Actualizar los precios según el plan
                if parking_lot.subscription_plan.plan_type == 'MENSUAL':
                    parking_lot.monthly_price = parking_lot.subscription_plan.price
                elif parking_lot.subscription_plan.plan_type == 'ANUAL':
                    parking_lot.annual_price = parking_lot.subscription_plan.price
                    parking_lot.monthly_price = parking_lot.subscription_plan.price / 12
            
            parking_lot.save()
            
            # Actualizar email del usuario si cambió
            if 'email' in form.changed_data:
                parking_lot.user.email = form.cleaned_data['email']
                parking_lot.user.username = form.cleaned_data['email']
                parking_lot.user.save()
            
            # Actualizar contraseña si se proporcionó
            new_password = request.POST.get('new_password')
            if new_password:
                parking_lot.user.set_password(new_password)
                parking_lot.user.save()
                messages.success(request, 'Contraseña actualizada correctamente.')
            
            messages.success(request, f'Parqueadero "{parking_lot.empresa}" actualizado exitosamente.')
            return redirect('superadmin_dashboard')
    else:
        form = ParkingLotEditForm(instance=parking_lot)
    
    return render(request, 'parking/superadmin/edit_parking_lot.html', {
        'form': form,
        'parking_lot': parking_lot
    })


@superuser_required
def toggle_parking_lot_status(request, pk):
    """Activar/desactivar un parqueadero"""
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    parking_lot.is_active = not parking_lot.is_active
    parking_lot.save()
    
    # También desactivar el usuario
    parking_lot.user.is_active = parking_lot.is_active
    parking_lot.user.save()
    
    status = 'activado' if parking_lot.is_active else 'desactivado'
    messages.success(request, f'Parqueadero "{parking_lot.empresa}" {status} exitosamente.')
    return redirect('superadmin_dashboard')


@superuser_required
def renew_subscription(request, pk):
    """Renovar suscripción de un parqueadero"""
    from django.utils import timezone
    from datetime import timedelta
    
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    
    if request.method == 'POST':
        # Obtener la fecha de inicio (hoy o la fecha de vencimiento si aún no ha vencido)
        today = timezone.now().date()
        
        if parking_lot.subscription_end and parking_lot.subscription_end > today:
            # Si aún no ha vencido, extender desde la fecha de vencimiento
            start_date = parking_lot.subscription_end
        else:
            # Si ya venció, empezar desde hoy
            start_date = today
        
        # Calcular nueva fecha de vencimiento según el plan
        if parking_lot.plan_type == 'MENSUAL':
            new_end_date = start_date + timedelta(days=30)
        else:  # ANUAL
            new_end_date = start_date + timedelta(days=365)
        
        # Actualizar el parqueadero
        parking_lot.subscription_end = new_end_date
        parking_lot.payment_status = 'PAGADO'
        parking_lot.last_payment_date = today
        parking_lot.is_active = True
        parking_lot.save()
        
        # Activar el usuario también
        parking_lot.user.is_active = True
        parking_lot.user.save()
        
        messages.success(request, f'Suscripción de "{parking_lot.empresa}" renovada hasta {new_end_date.strftime("%d/%m/%Y")}.')
        return redirect('superadmin_dashboard')
    
    return render(request, 'parking/superadmin/renew_subscription.html', {
        'parking_lot': parking_lot
    })


@superuser_required
def delete_parking_lot(request, pk):
    """Eliminar un parqueadero"""
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    
    if request.method == 'POST':
        empresa_name = parking_lot.empresa
        user = parking_lot.user
        parking_lot.delete()
        user.delete()
        messages.success(request, f'Parqueadero "{empresa_name}" eliminado exitosamente.')
        return redirect('superadmin_dashboard')
    
    return render(request, 'parking/superadmin/delete_parking_lot.html', {
        'parking_lot': parking_lot
    })



@superuser_required
def payment_management(request):
    """Vista para gestionar pagos de suscripciones"""
    parking_lots = ParkingLot.objects.all().select_related('user')
    
    # Obtener todos los pagos
    from .models import SubscriptionPayment
    payments = SubscriptionPayment.objects.all().select_related('parking_lot', 'processed_by').order_by('-payment_date')[:50]
    
    # Calcular estadísticas
    total_payments = SubscriptionPayment.objects.filter(status='APROBADO').count()
    total_revenue = SubscriptionPayment.objects.filter(status='APROBADO').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    pending_payments = parking_lots.filter(payment_status='PENDIENTE').count()
    
    context = {
        'parking_lots': parking_lots,
        'payments': payments,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments,
    }
    return render(request, 'parking/superadmin/payment_management.html', context)


@superuser_required
def register_payment(request, pk):
    """Registrar un pago de suscripción"""
    from .models import SubscriptionPayment
    from django.db import models as django_models
    
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        try:
            amount = float(amount)
            
            # Calcular fechas de suscripción
            today = timezone.now().date()
            
            # Si tiene suscripción activa, extender desde la fecha de vencimiento
            if parking_lot.subscription_end and parking_lot.subscription_end > today:
                start_date = parking_lot.subscription_end
            else:
                start_date = today
            
            # Calcular fecha de fin según el plan
            if parking_lot.plan_type == 'MENSUAL':
                end_date = start_date + timedelta(days=30)
            else:  # ANUAL
                end_date = start_date + timedelta(days=365)
            
            # Crear el registro de pago
            payment = SubscriptionPayment.objects.create(
                parking_lot=parking_lot,
                amount=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                status='APROBADO',
                processed_by=request.user,
                subscription_start=start_date,
                subscription_end=end_date,
                plan_type=parking_lot.plan_type
            )
            
            # Actualizar el parqueadero
            parking_lot.subscription_end = end_date
            if not parking_lot.subscription_start:
                parking_lot.subscription_start = start_date
            parking_lot.payment_status = 'PAGADO'
            parking_lot.last_payment_date = today
            parking_lot.is_active = True
            parking_lot.save()
            
            # Activar el usuario
            parking_lot.user.is_active = True
            parking_lot.user.save()
            
            messages.success(request, f'Pago registrado exitosamente. Suscripción extendida hasta {end_date.strftime("%d/%m/%Y")}.')
            return redirect('payment_management')
            
        except ValueError:
            messages.error(request, 'Monto inválido.')
        except Exception as e:
            messages.error(request, f'Error al registrar el pago: {str(e)}')
    
    context = {
        'parking_lot': parking_lot,
    }
    return render(request, 'parking/superadmin/register_payment.html', context)


@superuser_required
def payment_history(request, pk):
    """Ver historial de pagos de un parqueadero"""
    from .models import SubscriptionPayment
    
    parking_lot = get_object_or_404(ParkingLot, pk=pk)
    payments = SubscriptionPayment.objects.filter(parking_lot=parking_lot).select_related('processed_by').order_by('-payment_date')
    
    total_paid = payments.filter(status='APROBADO').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    context = {
        'parking_lot': parking_lot,
        'payments': payments,
        'total_paid': total_paid,
    }
    return render(request, 'parking/superadmin/payment_history.html', context)



@superuser_required
def subscription_plans(request):
    """Vista para gestionar planes de suscripción"""
    from .models import SubscriptionPlan
    
    plans = SubscriptionPlan.objects.all().order_by('duration_days')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            plan_type = request.POST.get('plan_type')
            price = request.POST.get('price')
            duration_days = request.POST.get('duration_days')
            description = request.POST.get('description', '')
            
            try:
                SubscriptionPlan.objects.create(
                    name=name,
                    plan_type=plan_type,
                    price=price,
                    duration_days=duration_days,
                    description=description
                )
                messages.success(request, f'Plan "{name}" creado exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al crear el plan: {str(e)}')
        
        elif action == 'update':
            plan_id = request.POST.get('plan_id')
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                plan.name = request.POST.get('name')
                plan.price = request.POST.get('price')
                plan.duration_days = request.POST.get('duration_days')
                plan.description = request.POST.get('description', '')
                plan.is_active = request.POST.get('is_active') == 'on'
                plan.save()
                messages.success(request, f'Plan "{plan.name}" actualizado exitosamente.')
            except Exception as e:
                messages.error(request, f'Error al actualizar el plan: {str(e)}')
        
        return redirect('subscription_plans')
    
    context = {
        'plans': plans,
    }
    return render(request, 'parking/superadmin/subscription_plans.html', context)
