# Python standard library
from datetime import datetime, timedelta

# Django core
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import IntegrityError, models, transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now

# Django database
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Extract, TruncDate

# Django views
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.views.generic.edit import DeleteView

# Local imports
from .forms import CategoryForm, ParkingLotForm, ParkingTicketForm
from .models import ParkingLot, ParkingTicket, VehicleCategory, Caja, Cliente, Mensualidad, PaymentMethod
from .services import ReportService, TicketService, CashRegisterService, SecurityService
from .utils import require_parking_lot, require_active_subscription, sanitize_plate


@login_required
def pagina_inicial(request):
    if request.user.is_authenticated:
        # Redirigir según el tipo de usuario
        if request.user.is_superuser:
            return redirect('superadmin_dashboard')
        return redirect('dashboard')
    
    return render(request, 'registration/login.html')


class ParkingLotUpdateView(UpdateView):
    model = ParkingLot
    template_name = 'parking/parking_lot_form.html'
    fields = ['nombre', 'nit', 'telefono', 'direccion']
    success_url = reverse_lazy('dashboard')


class CategoryListView(ListView):
    model = VehicleCategory
    template_name = 'parking/category_list.html'
    
    def get_queryset(self):
        if self.request.current_parking_lot:
            return VehicleCategory.objects.filter(parking_lot=self.request.current_parking_lot)
        return VehicleCategory.objects.none()


class CategoryCreateView(CreateView):
    model = VehicleCategory
    form_class = CategoryForm
    template_name = 'parking/category_form.html'
    success_url = reverse_lazy('category-list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['parking_lot'] = self.request.current_parking_lot
        return kwargs

    def form_valid(self, form):
        if not self.request.current_parking_lot:
            messages.error(self.request, 'No tienes un parqueadero asignado.')
            return self.form_invalid(form)
        
        form.instance.parking_lot = self.request.current_parking_lot
        messages.success(self.request, "Categoría creada con éxito.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error al crear la categoría.")
        return super().form_invalid(form)


class VehicleEntryView(CreateView):
    model = ParkingTicket
    form_class = ParkingTicketForm
    template_name = 'parking/vehicle_entry.html'
    success_url = reverse_lazy('print-ticket')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrar categorías por el parqueadero actual
        if self.request.current_parking_lot:
            form.fields['category'].queryset = VehicleCategory.objects.filter(
                parking_lot=self.request.current_parking_lot
            )
        return form

    def form_valid(self, form):
        try:
            if not self.request.current_parking_lot:
                messages.error(self.request, 'No tienes un parqueadero asignado.')
                return self.form_invalid(form)
            
            form.instance.parking_lot = self.request.current_parking_lot
            category = form.cleaned_data['category']
            if category.name.upper() == 'MOTOS':
                cascos = self.request.POST.get('cascos', 0)
                form.instance.cascos = int(cascos)
            response = super().form_valid(form)
            self.request.session['ticket_id'] = str(self.object.id)
            return response
        except IntegrityError:
            messages.error(self.request, 'Este vehículo ya se encuentra en el estacionamiento.')
            return self.form_invalid(form)


@login_required
@require_parking_lot
@require_active_subscription
def vehicle_exit(request):
    parking_lot = request.current_parking_lot
    
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        
        if not identifier:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Placa no válida'}, status=400)
            messages.error(request, 'Placa no válida')
            return redirect('vehicle-exit')
        
        # SEGURIDAD: Buscar por placa o por ID (código de barras)
        # Primero intentar buscar por placa
        ticket = ParkingTicket.objects.select_related('category', 'parking_lot').filter(
            parking_lot=parking_lot,
            placa__iexact=identifier,
            exit_time__isnull=True
        ).first()
        
        # Si no se encuentra por placa, intentar buscar por ID (código de barras)
        if not ticket:
            try:
                # El código de barras puede contener el ID del ticket
                ticket = ParkingTicket.objects.select_related('category', 'parking_lot').filter(
                    parking_lot=parking_lot,
                    id=identifier,
                    exit_time__isnull=True
                ).first()
            except (ValueError, TypeError):
                pass

        if ticket:
            try:
                # NO registrar la salida aún, solo calcular el monto
                # La salida se registrará cuando se confirme el pago en print_exit_ticket
                amount_to_pay = ticket.calculate_current_fee()
                duration_hours = ticket.get_current_duration()

                # Para solicitudes AJAX (primer formulario)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'amount': float(amount_to_pay),
                        'duration': duration_hours['hours'],
                        'placa': ticket.placa,
                        'entry_time': ticket.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'ticket_id': str(ticket.id)
                    })

            except Exception as e:
                # Log del error para debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error en vehicle_exit: {str(e)}', exc_info=True)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Error al procesar la solicitud'}, status=500)
                messages.error(request, 'Error al procesar la solicitud')
                return redirect('vehicle-exit')

        # Si no se encuentra el ticket
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Vehículo no encontrado o ya tiene salida registrada'}, status=404)
        messages.error(request, 'Vehículo no encontrado o ya tiene salida registrada')
        return redirect('vehicle-exit')

    # Para solicitudes GET
    placa = request.GET.get('placa', '').strip()
    
    # OPTIMIZACIÓN: Obtener medios de pago activos
    payment_methods = parking_lot.payment_methods.filter(is_active=True).order_by('orden', 'nombre')
    
    return render(request, 'parking/vehicle_exit.html', {
        'placa': placa,
        'payment_methods': payment_methods,
    })


@login_required
@require_parking_lot
@require_active_subscription
def print_exit_ticket(request):
    if request.method != 'POST':
        messages.warning(request, 'Método no permitido')
        return redirect('dashboard')
    
    ticket_id = request.POST.get('ticket_id')
    amount_received = request.POST.get('amount_received')
    payment_method_id = request.POST.get('payment_method')

    if not ticket_id or not amount_received:
        messages.error(request, 'Datos incompletos')
        return redirect('vehicle-exit')

    try:
        # Validar monto recibido
        amount_received_decimal = float(amount_received)
        if amount_received_decimal < 0:
            messages.error(request, 'El monto recibido no puede ser negativo')
            return redirect('vehicle-exit')
        
        # SEGURIDAD: Usar transaction.atomic para garantizar consistencia
        with transaction.atomic():
            # SEGURIDAD: Verificar que el ticket pertenece al parqueadero del usuario
            # Usar select_for_update para evitar race conditions
            ticket = ParkingTicket.objects.select_for_update().select_related('category', 'parking_lot').get(
                id=ticket_id,
                parking_lot=request.current_parking_lot,
                exit_time__isnull=True  # Asegurar que no tenga salida registrada
            )
            
            # Usar el servicio para registrar la salida
            ticket = TicketService.register_exit(ticket, payment_method_id)
            
            # Calcular el cambio
            amount_paid = float(ticket.amount_paid)
            change = amount_received_decimal - amount_paid
            
            # Invalidar caché del dashboard
            cache_key = f'dashboard_stats_{request.current_parking_lot.id}_{timezone.now().date()}'
            cache.delete(cache_key)

        return render(request, 'parking/print_exit_ticket.html', {
            'ticket': ticket,
            'parking_lot': request.current_parking_lot,
            'amount_received': amount_received_decimal,
            'change': change,
            'current_time': timezone.now(),
        })
        
    except ParkingTicket.DoesNotExist:
        messages.error(request, 'Ticket no encontrado, ya tiene salida registrada o no tienes permiso')
        return redirect('dashboard')
    except ValueError:
        messages.error(request, 'El monto recibido no es válido')
        return redirect('vehicle-exit')
    except Exception as e:
        # Log del error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error en print_exit_ticket: {str(e)}', exc_info=True)
        
        messages.error(request, 'Error al procesar la salida del vehículo')
        return redirect('dashboard')


@login_required
def dashboard(request):
    # Verificar que el usuario tenga un parqueadero asignado
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot
    today = timezone.now().date()
    
    # Definir el rango de los últimos 7 días
    start_date = today - timedelta(days=7)
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    
    # Usar caché para estadísticas (válido por 5 minutos)
    from django.core.cache import cache
    cache_key = f'dashboard_stats_{parking_lot.id}_{today}'
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        context = cached_stats
        context['current_time'] = timezone.now()
        return render(request, 'parking/dashboard.html', context)
    
    # Obtener tickets que entraron en los últimos 7 días (optimizado con only)
    recent_tickets_count = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        entry_time__gte=start_datetime,
        entry_time__lte=end_datetime
    ).count()

    # Obtener ingresos de tickets que salieron en los últimos 7 días (una sola consulta)
    tickets_aggregates = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__gte=start_datetime,
        exit_time__lte=end_datetime,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).aggregate(
        total_revenue=Sum('amount_paid'),
        total_count=Count('id')
    )
    
    # Obtener ingresos de mensualidades pagadas en los últimos 7 días (una sola consulta)
    mensualidades_aggregates = Mensualidad.objects.filter(
        parking_lot=parking_lot,
        fecha_pago__gte=start_datetime,
        fecha_pago__lte=end_datetime,
        estado='PAGADO'
    ).aggregate(
        total_revenue=Sum('monto'),
        total_count=Count('id')
    )
    
    # Calcular totales
    total_tickets_revenue = tickets_aggregates['total_revenue'] or 0
    total_mensualidades_revenue = mensualidades_aggregates['total_revenue'] or 0
    total_revenue = total_tickets_revenue + total_mensualidades_revenue

    # Obtener vehículos activos (sin salida) - optimizado con select_related
    active_vehicles = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__isnull=True
    ).select_related('category').only('id', 'placa', 'entry_time', 'category__name')

    # Estadísticas diarias de los últimos 7 días
    daily_stats = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__gte=start_datetime,
        exit_time__lte=end_datetime,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).extra(
        select={'date': 'DATE(exit_time)'}
    ).values('date').annotate(
        revenue=Sum('amount_paid'),
        count=Count('id')
    ).order_by('date')

    # Estadísticas por categoría de los últimos 7 días
    category_stats = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__gte=start_datetime,
        exit_time__lte=end_datetime,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).values('category__name').annotate(
        count=Count('id'),
        revenue=Sum('amount_paid')
    )

    # Estadísticas generales
    stats = {
        'daily': {
            'total_vehicles': recent_tickets_count,
            'total_revenue': total_revenue,
            'total_tickets_revenue': total_tickets_revenue,
            'total_mensualidades_revenue': total_mensualidades_revenue,
            'total_mensualidades_count': mensualidades_aggregates['total_count'] or 0
        },
        'category': category_stats,
        'active_vehicles': active_vehicles.count(),
        'active_vehicles_list': active_vehicles
    }

    # Verificar estado de suscripción
    subscription_alert = None
    if parking_lot.subscription_end:
        days_remaining = parking_lot.days_until_expiration()
        if days_remaining <= 5 and days_remaining >= 0:
            subscription_alert = {
                'days': days_remaining,
                'end_date': parking_lot.subscription_end,
                'type': 'warning' if days_remaining > 2 else 'danger'
            }
        elif days_remaining < 0:
            subscription_alert = {
                'days': days_remaining,
                'end_date': parking_lot.subscription_end,
                'type': 'expired'
            }
    
    context = {
        'stats': stats,
        'daily_stats': [
            {
                'date': datetime.strptime(str(stat['date']), '%Y-%m-%d').strftime('%d/%m/%Y'),
                'revenue': stat['revenue'] or 0,
                'count': stat['count'] or 0,
            }
            for stat in daily_stats
        ],
        'current_time': timezone.now(),
        'subscription_alert': subscription_alert
    }
    
    # Cachear por 5 minutos
    cache.set(cache_key, context, 300)

    return render(request, 'parking/dashboard.html', context)
@login_required
def print_ticket(request):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    ticket_id = request.GET.get('ticket_id') or request.session.get('ticket_id')
    
    if ticket_id:
        try:
            ticket = ParkingTicket.objects.get(
                id=ticket_id,
                parking_lot=request.current_parking_lot
            )
            parking_lot = request.current_parking_lot
            
            if 'ticket_id' in request.session:
                del request.session['ticket_id']
            
            return render(request, 'parking/print_ticket.html', {
                'ticket': ticket,
                'parking_lot': parking_lot,
                'is_reprint': bool(request.GET.get('ticket_id')),
                'current_time': timezone.now(),
                'duration': ticket.get_duration() if ticket.exit_time else ticket.get_current_duration(),
                'current_fee': ticket.amount_paid if ticket.exit_time else ticket.calculate_current_fee()
            })
        except ParkingTicket.DoesNotExist:
            messages.error(request, 'Ticket no encontrado')
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f'Error al imprimir ticket: {str(e)}')
            return redirect('dashboard')
    
    messages.warning(request, 'No se especificó un ticket para imprimir')
    return redirect('vehicle-entry')


class ReportView(TemplateView):
    template_name = 'parking/reports.html'

    def get(self, request, *args, **kwargs):
        # Verificar si se solicita exportación
        export_format = request.GET.get('export')
        
        if export_format in ['excel', 'pdf']:
            return self.export_report(request, export_format)
        
        return super().get(request, *args, **kwargs)

    def export_report(self, request, format_type):
        """Maneja la exportación de reportes a Excel o PDF"""
        from parking.reports import export_to_excel, export_to_pdf
        
        if not request.current_parking_lot:
            messages.error(request, 'No tienes un parqueadero asignado.')
            return redirect('reports')
        
        parking_lot = request.current_parking_lot
        
        # Obtener fechas del filtro
        filter_type = request.GET.get('filter_type', 'custom')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        today = now()
        
        # Aplicar filtros predefinidos
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
        elif filter_type == 'custom':
            if not start_date or not end_date:
                start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                start_date = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
                end_date = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
        
        # Obtener tickets
        tickets = ParkingTicket.objects.filter(
            parking_lot=parking_lot,
            exit_time__isnull=False,
            exit_time__range=(start_date, end_date)
        ).exclude(amount_paid__isnull=True).select_related('category', 'payment_method')
        
        # Obtener mensualidades pagadas en el período
        mensualidades = Mensualidad.objects.filter(
            parking_lot=parking_lot,
            fecha_pago__range=(start_date, end_date),
            estado='PAGADO'
        ).select_related('cliente', 'category', 'payment_method')
        
        # Resumen por medio de pago (tickets)
        payment_summary_tickets = tickets.values('payment_method__nombre').annotate(
            count=Count('id'),
            total=Sum('amount_paid')
        )
        
        # Resumen por medio de pago (mensualidades)
        payment_summary_mensualidades = mensualidades.values('payment_method__nombre').annotate(
            count=Count('id'),
            total=Sum('monto')
        )
        
        # Combinar ambos resúmenes
        payment_summary_dict = {}
        for payment in payment_summary_tickets:
            nombre = payment['payment_method__nombre'] or 'Sin especificar'
            payment_summary_dict[nombre] = {
                'payment_method__nombre': nombre,
                'count': payment['count'],
                'total': payment['total'] or 0
            }
        
        for payment in payment_summary_mensualidades:
            nombre = payment['payment_method__nombre'] or 'Sin especificar'
            if nombre in payment_summary_dict:
                payment_summary_dict[nombre]['count'] += payment['count']
                payment_summary_dict[nombre]['total'] += payment['total'] or 0
            else:
                payment_summary_dict[nombre] = {
                    'payment_method__nombre': nombre,
                    'count': payment['count'],
                    'total': payment['total'] or 0
                }
        
        payment_summary = sorted(payment_summary_dict.values(), key=lambda x: x['total'], reverse=True)
        
        # Estadísticas por categoría
        category_stats = tickets.values('category__name').annotate(
            count=Count('id'),
            revenue=Sum('amount_paid')
        ).order_by('-count')
        
        # Generar archivo
        if format_type == 'excel':
            output = export_to_excel(parking_lot, start_date, end_date, tickets, payment_summary, category_stats, mensualidades)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f'reporte_{parking_lot.empresa}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.xlsx'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        elif format_type == 'pdf':
            output = export_to_pdf(parking_lot, start_date, end_date, tickets, payment_summary, category_stats, mensualidades)
            response = HttpResponse(output.read(), content_type='application/pdf')
            filename = f'reporte_{parking_lot.empresa}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if not self.request.current_parking_lot:
            return context

        parking_lot = self.request.current_parking_lot

        # Manejo de filtros
        filter_type = self.request.GET.get('filter_type', 'custom')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        today = now()
        
        # Aplicar filtros predefinidos
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
        elif filter_type == 'custom':
            if not start_date or not end_date:
                start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            else:
                start_date = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
                end_date = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')

        # Obtener tickets completados (filtrado por parqueadero)
        tickets = ParkingTicket.objects.filter(
            parking_lot=parking_lot,
            exit_time__isnull=False,
            exit_time__range=(start_date, end_date)
        ).exclude(amount_paid__isnull=True)
        
        # Obtener mensualidades pagadas en el período
        mensualidades = Mensualidad.objects.filter(
            parking_lot=parking_lot,
            fecha_pago__range=(start_date, end_date),
            estado='PAGADO'
        )

        # Resumen general (tickets)
        summary_tickets = tickets.aggregate(
            total_vehicles=Count('id'),
            total_revenue=Sum('amount_paid'),
            avg_duration=Avg(F('exit_time') - F('entry_time')),
            avg_revenue=Avg('amount_paid')
        )
        
        # Resumen general (mensualidades)
        summary_mensualidades = mensualidades.aggregate(
            total_mensualidades=Count('id'),
            total_revenue_mensualidades=Sum('monto')
        )
        
        # Combinar resúmenes
        summary = {
            'total_vehicles': summary_tickets['total_vehicles'] or 0,
            'total_mensualidades': summary_mensualidades['total_mensualidades'] or 0,
            'total_revenue': (summary_tickets['total_revenue'] or 0) + (summary_mensualidades['total_revenue_mensualidades'] or 0),
            'total_revenue_tickets': summary_tickets['total_revenue'] or 0,
            'total_revenue_mensualidades': summary_mensualidades['total_revenue_mensualidades'] or 0,
            'avg_duration': summary_tickets['avg_duration'],
            'avg_revenue': summary_tickets['avg_revenue']
        }

        if summary['avg_duration'] is not None:
            summary['avg_duration'] = summary['avg_duration'].total_seconds() / 3600

        # Estadísticas por categoría
        category_stats = []
        for stat in tickets.values('category__name').annotate(
            count=Count('id'),
            revenue=Sum('amount_paid'),
        ).order_by('-count'):
            category_tickets = tickets.filter(category__name=stat['category__name'])
            durations = [
                (ticket.exit_time - ticket.entry_time).total_seconds() / 3600
                for ticket in category_tickets
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            stat['avg_duration'] = avg_duration
            category_stats.append(stat)

        # Estadísticas diarias
        daily_stats = list(tickets.annotate(
            date=TruncDate('exit_time')
        ).values('date').annotate(
            count=Count('id'),
            revenue=Sum('amount_paid')
        ).order_by('date'))

        # Vehículos más frecuentes
        frequent_vehicles = tickets.values('placa').annotate(
            visits=Count('id'),
            total_spent=Sum('amount_paid')
        ).order_by('-visits')[:10]

        # Resumen por medio de pago (tickets)
        payment_summary_tickets = tickets.values('payment_method__nombre').annotate(
            count=Count('id'),
            total=Sum('amount_paid')
        )
        
        # Resumen por medio de pago (mensualidades)
        payment_summary_mensualidades = mensualidades.values('payment_method__nombre').annotate(
            count=Count('id'),
            total=Sum('monto')
        )
        
        # Combinar ambos resúmenes
        payment_summary_dict = {}
        for payment in payment_summary_tickets:
            nombre = payment['payment_method__nombre'] or 'Sin especificar'
            payment_summary_dict[nombre] = {
                'payment_method__nombre': nombre,
                'count': payment['count'],
                'total': payment['total'] or 0
            }
        
        for payment in payment_summary_mensualidades:
            nombre = payment['payment_method__nombre'] or 'Sin especificar'
            if nombre in payment_summary_dict:
                payment_summary_dict[nombre]['count'] += payment['count']
                payment_summary_dict[nombre]['total'] += payment['total'] or 0
            else:
                payment_summary_dict[nombre] = {
                    'payment_method__nombre': nombre,
                    'count': payment['count'],
                    'total': payment['total'] or 0
                }
        
        payment_summary = sorted(payment_summary_dict.values(), key=lambda x: x['total'], reverse=True)

        # Datos para gráficos avanzados
        from parking.reports import generate_chart_data
        chart_data = generate_chart_data(tickets, start_date, end_date)
        
        # Registros recientes para la tabla
        recent_records = tickets.select_related('category', 'payment_method').order_by('-exit_time')[:50]

        context.update({
            'filter_type': filter_type,
            'start_date': start_date,
            'end_date': end_date,
            'summary': summary,
            'category_stats': category_stats,
            'daily_stats': daily_stats,
            'frequent_vehicles': frequent_vehicles,
            'payment_summary': payment_summary,
            'chart_data': chart_data,
            'recent_records': recent_records,
            'parking_lot': parking_lot
        })
        return context


@login_required
def company_profile(request):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot

    if request.method == 'POST':
        form = ParkingLotForm(request.POST, instance=parking_lot)
        if form.is_valid():
            form.save()
            messages.success(request, 'Información de la empresa actualizada correctamente.')
            return redirect('company_profile')
    else:
        form = ParkingLotForm(instance=parking_lot)

    return render(request, 'parking/company_profile.html', {'form': form})


def custom_logout(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('login')


@login_required
def category_edit(request, pk):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    # SEGURIDAD: Verificar que la categoría pertenece al parqueadero del usuario
    category = get_object_or_404(
        VehicleCategory,
        pk=pk,
        parking_lot=request.current_parking_lot
    )

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, parking_lot=request.current_parking_lot)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría actualizada correctamente.")
            return redirect('category-list')
        else:
            messages.error(request, "Hubo un error al actualizar la categoría.")
    else:
        form = CategoryForm(instance=category, parking_lot=request.current_parking_lot)

    return render(request, 'parking/category_edit.html', {
        'form': form,
        'object': category
    })


def validate_plate(request, plate):
    if not request.current_parking_lot:
        return JsonResponse({'exists': False})
    
    exists = ParkingTicket.objects.filter(
        parking_lot=request.current_parking_lot,
        placa__iexact=plate,
        exit_time__isnull=True
    ).exists()
    return JsonResponse({'exists': exists})


class CategoryDeleteView(DeleteView):
    model = VehicleCategory
    success_url = reverse_lazy('category-list')
    template_name = 'parking/category_confirm_delete.html'

    def get_queryset(self):
        # SEGURIDAD: Solo permitir eliminar categorías del parqueadero del usuario
        if self.request.current_parking_lot:
            return VehicleCategory.objects.filter(parking_lot=self.request.current_parking_lot)
        return VehicleCategory.objects.none()

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Categoría eliminada exitosamente')
        return super().delete(request, *args, **kwargs)

@login_required
@require_parking_lot
@require_active_subscription
def cash_register(request):
    parking_lot = request.current_parking_lot
    
    # Determinar si el usuario es vendedor
    is_vendedor = request.user.groups.filter(name='Vendedor').exists()

    # Manejo de fechas usando el servicio
    today = timezone.now().date()

    if is_vendedor:
        # Vendedores solo ven el día actual
        start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_date = start_date + timedelta(days=1)
    else:
        # Administradores pueden filtrar por fechas
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if start_date_str and end_date_str:
            try:
                start_date = timezone.make_aware(datetime.strptime(f"{start_date_str} 00:00:00", '%Y-%m-%d %H:%M:%S'))
                end_date = timezone.make_aware(datetime.strptime(f"{end_date_str} 23:59:59", '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                # Si las fechas no son válidas, usar el día actual
                start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
                end_date = start_date + timedelta(days=1)
        else:
            # Si no se proporcionan fechas, usar el día actual
            start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end_date = start_date + timedelta(days=1)

    # OPTIMIZACIÓN: Usar agregaciones de base de datos en lugar de Python
    all_tickets = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__gte=start_date,
        exit_time__lt=end_date,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).select_related('payment_method')
    
    mensualidades_pagadas = Mensualidad.objects.filter(
        parking_lot=parking_lot,
        fecha_pago__gte=start_date,
        fecha_pago__lt=end_date,
        estado='PAGADO'
    ).select_related('payment_method')
    
    # Calcular totales usando agregaciones
    tickets_aggregates = all_tickets.aggregate(total=Sum('amount_paid'))
    mensualidades_aggregates = mensualidades_pagadas.aggregate(total=Sum('monto'))
    
    total_tickets = tickets_aggregates['total'] or 0
    total_mensualidades = mensualidades_aggregates['total'] or 0
    total_general = total_tickets + total_mensualidades
    
    # Usar el servicio para calcular el total en efectivo
    total_efectivo = CashRegisterService.calculate_cash_total(parking_lot, start_date, end_date)
    
    # Obtener el medio de pago "Efectivo" para filtrar
    efectivo_method = PaymentMethod.objects.filter(
        parking_lot=parking_lot,
        nombre__iexact='efectivo'
    ).first()
    
    # Filtrar tickets y mensualidades de efectivo
    tickets_efectivo = all_tickets.filter(payment_method=efectivo_method)
    mensualidades_efectivo = mensualidades_pagadas.filter(payment_method=efectivo_method)
    
    # Usar el servicio para obtener el resumen por medio de pago
    payment_summary_list = ReportService.get_payment_method_summary(parking_lot, start_date, end_date)
    
    # Agregar información de si es efectivo
    for payment in payment_summary_list:
        payment['is_efectivo'] = payment['nombre'] and payment['nombre'].lower() == 'efectivo'
        payment['payment_method__nombre'] = payment['nombre']
        payment['payment_method__icono'] = payment['icono']

    # Usar el servicio para obtener o crear la caja
    caja_date = start_date.date()
    caja = CashRegisterService.get_or_create_caja(parking_lot, caja_date)
    
    # Actualizar el monto con el total de efectivo
    caja.monto = total_efectivo
    caja.descripcion = f'Ingresos en efectivo del período {start_date.date()} a {end_date.date()}'
    caja.save()

    # Calcular el dinero esperado (dinero_inicial + total_efectivo)
    dinero_esperado = float(caja.dinero_inicial) + float(total_efectivo)

    # Manejar el formulario para establecer el dinero inicial (base para vueltos)
    if request.method == 'POST' and 'set_dinero_inicial' in request.POST:
        try:
            dinero_inicial = float(request.POST.get('dinero_inicial', 0))
            if dinero_inicial < 0:
                messages.error(request, 'El dinero inicial no puede ser negativo.')
            else:
                caja.dinero_inicial = dinero_inicial
                caja.save()
                messages.success(request, 'Dinero inicial establecido correctamente.')
            return redirect('cash_register')
        except ValueError:
            messages.error(request, 'Por favor, ingrese un valor numérico válido para el dinero inicial.')

    # Manejar el formulario para el cuadre de caja
    if request.method == 'POST' and 'realizar_cuadre' in request.POST:
        try:
            dinero_final = float(request.POST.get('dinero_final', 0))
            if dinero_final < 0:
                messages.error(request, 'El dinero final no puede ser negativo.')
                return redirect('cash_register')

            # Usar el servicio para realizar el cuadre
            result = CashRegisterService.realizar_cuadre(caja, dinero_final)
            
            if result['success']:
                messages.success(request, 'Cuadre de caja realizado con éxito.')
            else:
                messages.error(request, result['message'])
            
            return redirect('cash_register')
        except ValueError:
            messages.error(request, 'Por favor, ingrese un valor numérico válido para el dinero final.')

    # Calcular diferencia si el cuadre ya fue realizado
    diferencia = None
    diferencia_abs = None
    if caja.cuadre_realizado:
        diferencia = (caja.dinero_final - caja.dinero_inicial) - total_efectivo
        diferencia_abs = abs(diferencia)  # Calcular el valor absoluto

    context = {
        'today': today,
        'start_date': start_date.date(),
        'end_date': (end_date - timedelta(days=1)).date(),
        'tickets': tickets_efectivo,
        'mensualidades': mensualidades_efectivo,
        'total_tickets': total_tickets,
        'total_mensualidades': total_mensualidades,
        'total_income': total_efectivo,
        'total_general': total_general,
        'payment_summary': payment_summary_list,
        'caja': caja,
        'dinero_esperado': dinero_esperado,
        'diferencia': diferencia,
        'diferencia_abs': diferencia_abs,
        'is_vendedor': is_vendedor,
    }
    return render(request, 'parking/cash_register.html', context)

# ==================== VISTAS DE CLIENTES ====================

@login_required
@require_parking_lot
def cliente_list(request):
    # OPTIMIZACIÓN: Solo traer los campos necesarios
    clientes = Cliente.objects.filter(
        parking_lot=request.current_parking_lot, 
        is_active=True
    ).only('id', 'nombre', 'documento', 'telefono', 'email', 'placa')
    
    return render(request, 'parking/cliente_list.html', {'clientes': clientes})


@login_required
@require_parking_lot
def cliente_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        documento = request.POST.get('documento', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        placa = sanitize_plate(request.POST.get('placa', ''))
        
        # Validaciones
        if not nombre or not documento:
            messages.error(request, 'El nombre y documento son obligatorios.')
            return render(request, 'parking/cliente_form.html')
        
        # SEGURIDAD: Verificar si ya existe un cliente con ese documento
        if Cliente.objects.filter(parking_lot=request.current_parking_lot, documento=documento).exists():
            messages.error(request, 'Ya existe un cliente con ese documento.')
            return render(request, 'parking/cliente_form.html')
        
        try:
            with transaction.atomic():
                cliente = Cliente.objects.create(
                    parking_lot=request.current_parking_lot,
                    nombre=nombre,
                    documento=documento,
                    telefono=telefono,
                    email=email,
                    direccion=direccion,
                    placa=placa
                )
            messages.success(request, 'Cliente creado exitosamente.')
            return redirect('cliente-list')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al crear cliente: {str(e)}', exc_info=True)
            messages.error(request, 'Error al crear el cliente.')
    
    return render(request, 'parking/cliente_form.html')


@login_required
@require_parking_lot
def cliente_edit(request, pk):
    # SEGURIDAD: Verificar que el cliente pertenece al parqueadero del usuario
    cliente = get_object_or_404(Cliente, pk=pk, parking_lot=request.current_parking_lot)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre es obligatorio.')
            return render(request, 'parking/cliente_edit.html', {'cliente': cliente})
        
        try:
            with transaction.atomic():
                cliente.nombre = nombre
                cliente.telefono = request.POST.get('telefono', '').strip()
                cliente.email = request.POST.get('email', '').strip()
                cliente.direccion = request.POST.get('direccion', '').strip()
                cliente.placa = sanitize_plate(request.POST.get('placa', ''))
                cliente.save()
            
            messages.success(request, 'Cliente actualizado exitosamente.')
            return redirect('cliente-list')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al actualizar cliente: {str(e)}', exc_info=True)
            messages.error(request, 'Error al actualizar el cliente.')
    
    return render(request, 'parking/cliente_edit.html', {'cliente': cliente})


@login_required
@require_parking_lot
def cliente_delete(request, pk):
    # SEGURIDAD: Verificar que el cliente pertenece al parqueadero del usuario
    cliente = get_object_or_404(Cliente, pk=pk, parking_lot=request.current_parking_lot)
    
    try:
        with transaction.atomic():
            cliente.is_active = False
            cliente.save()
        messages.success(request, 'Cliente eliminado exitosamente.')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error al eliminar cliente: {str(e)}', exc_info=True)
        messages.error(request, 'Error al eliminar el cliente.')
    
    return redirect('cliente-list')


# ==================== VISTAS DE MENSUALIDADES ====================

@login_required
@require_parking_lot
def mensualidad_list(request):
    # OPTIMIZACIÓN: Usar select_related para evitar N+1 queries
    mensualidades = Mensualidad.objects.filter(
        parking_lot=request.current_parking_lot
    ).select_related('cliente', 'category', 'payment_method').order_by('-fecha_inicio')
    
    # OPTIMIZACIÓN: Actualizar estados vencidos en una sola operación
    # En lugar de iterar, usar update para mensualidades vencidas
    from django.db.models import Q
    today = timezone.now().date()
    
    Mensualidad.objects.filter(
        parking_lot=request.current_parking_lot,
        fecha_vencimiento__lt=today,
        estado='PENDIENTE'
    ).update(estado='VENCIDO')
    
    # Refrescar el queryset después de la actualización
    mensualidades = mensualidades.all()
    
    return render(request, 'parking/mensualidad_list.html', {'mensualidades': mensualidades})


@login_required
def mensualidad_create(request):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    clientes = Cliente.objects.filter(parking_lot=request.current_parking_lot, is_active=True)
    categories = VehicleCategory.objects.filter(parking_lot=request.current_parking_lot, is_monthly=True)
    
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        category_id = request.POST.get('category')
        fecha_inicio = request.POST.get('fecha_inicio')
        estado = request.POST.get('estado', 'PENDIENTE')
        
        cliente = get_object_or_404(Cliente, pk=cliente_id, parking_lot=request.current_parking_lot)
        category = get_object_or_404(VehicleCategory, pk=category_id, parking_lot=request.current_parking_lot)
        
        # Calcular fecha de vencimiento (30 días después)
        fecha_inicio_dt = timezone.datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_vencimiento = fecha_inicio_dt + timedelta(days=30)
        
        mensualidad = Mensualidad.objects.create(
            parking_lot=request.current_parking_lot,
            cliente=cliente,
            category=category,
            fecha_inicio=fecha_inicio_dt,
            fecha_vencimiento=fecha_vencimiento,
            monto=category.monthly_rate,
            estado=estado
        )
        
        # Si se marca como pagado, registrar la fecha de pago
        if estado == 'PAGADO':
            mensualidad.fecha_pago = timezone.now()
            mensualidad.save()
        
        messages.success(request, 'Mensualidad creada exitosamente.')
        return redirect('mensualidad-list')
    
    return render(request, 'parking/mensualidad_form.html', {
        'clientes': clientes,
        'categories': categories
    })


@login_required
def mensualidad_pagar(request, pk):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    mensualidad = get_object_or_404(Mensualidad, pk=pk, parking_lot=request.current_parking_lot)
    
    # Obtener medios de pago activos
    payment_methods = PaymentMethod.objects.filter(
        parking_lot=request.current_parking_lot,
        is_active=True
    ).order_by('orden', 'nombre')
    
    if request.method == 'POST':
        payment_method_id = request.POST.get('payment_method')
        
        # Obtener el medio de pago seleccionado
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id,
                    parking_lot=request.current_parking_lot
                )
                mensualidad.payment_method = payment_method
            except PaymentMethod.DoesNotExist:
                messages.error(request, 'Medio de pago no válido.')
                return redirect('mensualidad-pagar', pk=pk)
        
        # Marcar como pagado (esto establece estado='PAGADO' y fecha_pago=now())
        mensualidad.estado = 'PAGADO'
        mensualidad.fecha_pago = timezone.now()
        mensualidad.save()
        
        messages.success(request, 'Mensualidad marcada como pagada.')
        return redirect('mensualidad-list')
    
    return render(request, 'parking/mensualidad_pagar.html', {
        'mensualidad': mensualidad,
        'payment_methods': payment_methods
    })


@login_required
def mensualidad_detail(request, pk):
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    mensualidad = get_object_or_404(Mensualidad, pk=pk, parking_lot=request.current_parking_lot)
    return render(request, 'parking/mensualidad_detail.html', {'mensualidad': mensualidad})


# ==================== VISTAS DE MEDIOS DE PAGO ====================

@login_required
def payment_method_list(request):
    """Lista de medios de pago"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot
    payment_methods = parking_lot.payment_methods.all().order_by('orden', 'nombre')
    
    context = {
        'payment_methods': payment_methods,
    }
    return render(request, 'parking/payment_method_list.html', context)


@login_required
def payment_method_create(request):
    """Crear nuevo medio de pago"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot
    
    if request.method == 'POST':
        try:
            from .models import PaymentMethod
            
            payment_method = PaymentMethod.objects.create(
                parking_lot=parking_lot,
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion', ''),
                icono=request.POST.get('icono', 'fa-money-bill-wave'),
                color=request.POST.get('color', 'primary'),
                orden=int(request.POST.get('orden', 0)),
                is_active=request.POST.get('is_active') == 'on'
            )
            
            messages.success(request, f'Medio de pago "{payment_method.nombre}" creado exitosamente.')
            return redirect('payment-method-list')
        except IntegrityError:
            messages.error(request, 'Ya existe un medio de pago con ese nombre.')
        except Exception as e:
            messages.error(request, f'Error al crear el medio de pago: {str(e)}')
    
    # Iconos disponibles
    iconos = [
        {'value': 'fa-money-bill-wave', 'label': 'Efectivo'},
        {'value': 'fa-mobile-alt', 'label': 'Móvil'},
        {'value': 'fa-credit-card', 'label': 'Tarjeta'},
        {'value': 'fa-university', 'label': 'Banco'},
        {'value': 'fa-qrcode', 'label': 'QR'},
        {'value': 'fa-wallet', 'label': 'Billetera'},
        {'value': 'fa-exchange-alt', 'label': 'Transferencia'},
        {'value': 'fa-hand-holding-usd', 'label': 'Pago'},
    ]
    
    context = {
        'iconos': iconos,
    }
    return render(request, 'parking/payment_method_form.html', context)


@login_required
def payment_method_edit(request, pk):
    """Editar medio de pago"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    from .models import PaymentMethod
    payment_method = get_object_or_404(PaymentMethod, pk=pk, parking_lot=request.current_parking_lot)
    
    if request.method == 'POST':
        try:
            payment_method.nombre = request.POST.get('nombre')
            payment_method.descripcion = request.POST.get('descripcion', '')
            payment_method.icono = request.POST.get('icono', 'fa-money-bill-wave')
            payment_method.color = request.POST.get('color', 'primary')
            payment_method.orden = int(request.POST.get('orden', 0))
            payment_method.is_active = request.POST.get('is_active') == 'on'
            payment_method.save()
            
            messages.success(request, f'Medio de pago "{payment_method.nombre}" actualizado exitosamente.')
            return redirect('payment-method-list')
        except IntegrityError:
            messages.error(request, 'Ya existe un medio de pago con ese nombre.')
        except Exception as e:
            messages.error(request, f'Error al actualizar el medio de pago: {str(e)}')
    
    # Iconos disponibles
    iconos = [
        {'value': 'fa-money-bill-wave', 'label': 'Efectivo'},
        {'value': 'fa-mobile-alt', 'label': 'Móvil'},
        {'value': 'fa-credit-card', 'label': 'Tarjeta'},
        {'value': 'fa-university', 'label': 'Banco'},
        {'value': 'fa-qrcode', 'label': 'QR'},
        {'value': 'fa-wallet', 'label': 'Billetera'},
        {'value': 'fa-exchange-alt', 'label': 'Transferencia'},
        {'value': 'fa-hand-holding-usd', 'label': 'Pago'},
    ]
    
    context = {
        'payment_method': payment_method,
        'iconos': iconos,
    }
    return render(request, 'parking/payment_method_form.html', context)


@login_required
def payment_method_delete(request, pk):
    """Eliminar medio de pago"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    from .models import PaymentMethod
    payment_method = get_object_or_404(PaymentMethod, pk=pk, parking_lot=request.current_parking_lot)
    
    # Verificar si el medio de pago está siendo usado
    if payment_method.parkingticket_set.exists() or payment_method.mensualidad_set.exists():
        messages.error(request, 'No se puede eliminar este medio de pago porque está siendo utilizado en transacciones.')
        return redirect('payment-method-list')
    
    nombre = payment_method.nombre
    payment_method.delete()
    messages.success(request, f'Medio de pago "{nombre}" eliminado exitosamente.')
    return redirect('payment-method-list')


# ==================== REPORTES AVANZADOS ====================

@login_required
def advanced_reports(request):
    """Vista de reportes avanzados con filtros y exportación"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot
    
    # Obtener parámetros de filtro
    filter_type = request.GET.get('filter_type', 'today')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    payment_method_id = request.GET.get('payment_method')
    category_id = request.GET.get('category')
    export_format = request.GET.get('export')
    
    # Determinar rango de fechas según el filtro
    today = timezone.now().date()
    
    if filter_type == 'today':
        start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    elif filter_type == 'week':
        start_date = timezone.make_aware(datetime.combine(today - timedelta(days=7), datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    elif filter_type == 'month':
        start_date = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    elif filter_type == 'year':
        start_date = timezone.make_aware(datetime.combine(today.replace(month=1, day=1), datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    elif filter_type == 'custom' and start_date_str and end_date_str:
        try:
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(f"{end_date_str} 23:59:59", '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    else:
        start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    
    # Query base
    tickets = ParkingTicket.objects.filter(
        parking_lot=parking_lot,
        exit_time__gte=start_date,
        exit_time__lte=end_date,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).select_related('category', 'payment_method')
    
    # Aplicar filtros adicionales
    if payment_method_id:
        tickets = tickets.filter(payment_method_id=payment_method_id)
    
    if category_id:
        tickets = tickets.filter(category_id=category_id)
    
    # Estadísticas generales
    total_tickets = tickets.count()
    total_revenue = tickets.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    avg_revenue = tickets.aggregate(Avg('amount_paid'))['amount_paid__avg'] or 0
    
    # Resumen por medio de pago
    payment_summary = tickets.values(
        'payment_method__nombre',
        'payment_method__icono'
    ).annotate(
        total=Sum('amount_paid'),
        count=Count('id')
    ).order_by('-total')
    
    # Resumen por categoría
    category_stats = tickets.values(
        'category__name'
    ).annotate(
        count=Count('id'),
        revenue=Sum('amount_paid'),
        avg_duration=Avg(
            (models.F('exit_time') - models.F('entry_time'))
        )
    ).order_by('-revenue')
    
    # Estadísticas diarias
    daily_stats = tickets.extra(
        select={'date': 'DATE(exit_time)'}
    ).values('date').annotate(
        revenue=Sum('amount_paid'),
        count=Count('id')
    ).order_by('date')
    
    # Top 10 vehículos frecuentes
    frequent_vehicles = tickets.values('placa').annotate(
        visits=Count('id'),
        total_spent=Sum('amount_paid')
    ).order_by('-visits')[:10]
    
    # Obtener listas para filtros
    payment_methods = parking_lot.payment_methods.filter(is_active=True).order_by('orden')
    categories = parking_lot.categories.all().order_by('name')
    
    # Exportación
    if export_format == 'excel':
        from .reports import export_to_excel
        output = export_to_excel(parking_lot, start_date, end_date, tickets, payment_summary, category_stats)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'reporte_{parking_lot.empresa}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    elif export_format == 'pdf':
        from .reports import export_to_pdf
        buffer = export_to_pdf(parking_lot, start_date, end_date, tickets, payment_summary, category_stats)
        
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        filename = f'reporte_{parking_lot.empresa}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'filter_type': filter_type,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'avg_revenue': avg_revenue,
        'payment_summary': payment_summary,
        'category_stats': category_stats,
        'daily_stats': daily_stats,
        'frequent_vehicles': frequent_vehicles,
        'payment_methods': payment_methods,
        'categories': categories,
        'selected_payment_method': payment_method_id,
        'selected_category': category_id,
    }
    
    return render(request, 'parking/advanced_reports.html', context)
