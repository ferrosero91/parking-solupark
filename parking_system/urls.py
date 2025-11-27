from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from parking import views
from parking.views import (
    ParkingLotUpdateView, custom_logout, CategoryListView, CategoryCreateView,
    VehicleEntryView, vehicle_exit, print_ticket, print_exit_ticket, ReportView,
    company_profile, category_edit, cash_register
)
from parking import admin_views
from parking.views_users import user_list, user_create, user_edit, user_delete, user_toggle_status

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.pagina_inicial, name='pagina_inicial'),
    
    # Rutas del Superadministrador
    path('superadmin/login/', admin_views.superadmin_login, name='superadmin_login'),
    path('superadmin/', admin_views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/parking-lots/create/', admin_views.create_parking_lot, name='create_parking_lot'),
    path('superadmin/parking-lots/<int:pk>/edit/', admin_views.edit_parking_lot, name='edit_parking_lot'),
    path('superadmin/parking-lots/<int:pk>/renew/', admin_views.renew_subscription, name='renew_subscription'),
    path('superadmin/parking-lots/<int:pk>/toggle/', admin_views.toggle_parking_lot_status, name='toggle_parking_lot_status'),
    path('superadmin/parking-lots/<int:pk>/delete/', admin_views.delete_parking_lot, name='delete_parking_lot'),
    
    # Rutas de Gestión de Pagos
    path('superadmin/payments/', admin_views.payment_management, name='payment_management'),
    path('superadmin/payments/<int:pk>/register/', admin_views.register_payment, name='register_payment'),
    path('superadmin/payments/<int:pk>/history/', admin_views.payment_history, name='payment_history'),
    path('superadmin/subscription-plans/', admin_views.subscription_plans, name='subscription_plans'),
    
    # Rutas de usuarios normales (clientes)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('entry/', VehicleEntryView.as_view(), name='vehicle-entry'),
    path('exit/', vehicle_exit, name='vehicle-exit'),
    path('print-ticket/', print_ticket, name='print-ticket'),
    path('print-exit-ticket/', print_exit_ticket, name='print-exit-ticket'),
    path('reprint-ticket/<int:ticket_id>/', print_ticket, name='reprint-ticket'),
    path('parking-lot/<int:pk>/update/', ParkingLotUpdateView.as_view(), name='parking-lot-update'),
    path('mi-empresa/', company_profile, name='company_profile'),
    path('logout/', custom_logout, name='logout'),
    path('categorias/', CategoryListView.as_view(), name='category-list'),
    path('categorias/new/', CategoryCreateView.as_view(), name='category-create'),
    path('categorias/<int:pk>/editar/', category_edit, name='category-edit'),
    path('categorias/<int:pk>/eliminar/', views.CategoryDeleteView.as_view(), name='category-delete'),
    path('reports/', ReportView.as_view(), name='reports'),
    path('cash-register/', cash_register, name='cash_register'),
    path('validate-plate/<str:plate>/', views.validate_plate, name='validate-plate'),
    
    # Rutas de Clientes y Mensualidades
    path('clientes/', views.cliente_list, name='cliente-list'),
    path('clientes/nuevo/', views.cliente_create, name='cliente-create'),
    path('clientes/<int:pk>/editar/', views.cliente_edit, name='cliente-edit'),
    path('clientes/<int:pk>/eliminar/', views.cliente_delete, name='cliente-delete'),
    path('mensualidades/', views.mensualidad_list, name='mensualidad-list'),
    path('mensualidades/nueva/', views.mensualidad_create, name='mensualidad-create'),
    path('mensualidades/<int:pk>/pagar/', views.mensualidad_pagar, name='mensualidad-pagar'),
    path('mensualidades/<int:pk>/detalle/', views.mensualidad_detail, name='mensualidad-detail'),
    
    # Rutas de Medios de Pago
    path('medios-pago/', views.payment_method_list, name='payment-method-list'),
    path('medios-pago/nuevo/', views.payment_method_create, name='payment-method-create'),
    path('medios-pago/<int:pk>/editar/', views.payment_method_edit, name='payment-method-edit'),
    path('medios-pago/<int:pk>/eliminar/', views.payment_method_delete, name='payment-method-delete'),
    
    # Rutas de Gestión de Usuarios
    path('usuarios/', user_list, name='user-list'),
    path('usuarios/nuevo/', user_create, name='user-create'),
    path('usuarios/<int:pk>/editar/', user_edit, name='user-edit'),
    path('usuarios/<int:pk>/eliminar/', user_delete, name='user-delete'),
    path('usuarios/<int:pk>/toggle-status/', user_toggle_status, name='user-toggle-status'),
    
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)