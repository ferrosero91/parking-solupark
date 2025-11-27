# -*- coding: utf-8 -*-
"""
Vistas para gestión de usuarios y permisos
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q

from .forms_users import UserCreateForm, UserEditForm


def is_admin(user):
    """Verifica si el usuario es administrador"""
    return user.is_superuser or user.groups.filter(name__in=['Admin', 'Administrador']).exists() or user.is_staff


@login_required
@user_passes_test(is_admin)
def user_list(request):
    """Lista todos los usuarios del sistema"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    parking_lot = request.current_parking_lot
    
    # Buscar usuarios (excluir superusuarios y el usuario dueño del parqueadero)
    search_query = request.GET.get('search', '')
    
    # Obtener solo los usuarios asignados a este parqueadero
    from parking.models import UserParkingLot
    user_ids = UserParkingLot.objects.filter(
        parking_lot=parking_lot
    ).values_list('user_id', flat=True)
    
    users = User.objects.filter(
        id__in=user_ids,
        is_superuser=False
    ).order_by('-date_joined')
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Agregar información de rol a cada usuario
    users_with_roles = []
    for user in users:
        user_groups = list(user.groups.values_list('name', flat=True))
        
        # Determinar el rol del usuario
        if 'Admin' in user_groups or 'Administrador' in user_groups or user.is_staff:
            role = 'Administrador'
            role_class = 'bg-purple-100 text-purple-700'
            role_icon = 'fa-user-shield'
        elif 'Cajero' in user_groups:
            role = 'Cajero'
            role_class = 'bg-green-100 text-green-700'
            role_icon = 'fa-cash-register'
        elif 'Operador' in user_groups:
            role = 'Operador'
            role_class = 'bg-blue-100 text-blue-700'
            role_icon = 'fa-user'
        else:
            role = 'Sin rol'
            role_class = 'bg-gray-100 text-gray-700'
            role_icon = 'fa-user'
        
        users_with_roles.append({
            'user': user,
            'role': role,
            'role_class': role_class,
            'role_icon': role_icon
        })
    
    context = {
        'users_with_roles': users_with_roles,
        'search_query': search_query,
    }
    return render(request, 'parking/user_list.html', context)


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Crea un nuevo usuario"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Asignar el usuario al parqueadero actual
            from parking.models import UserParkingLot
            UserParkingLot.objects.create(
                user=user,
                parking_lot=request.current_parking_lot
            )
            
            messages.success(request, f'Usuario {user.username} creado exitosamente y asignado a {request.current_parking_lot.empresa}.')
            return redirect('user-list')
    else:
        form = UserCreateForm()
    
    return render(request, 'parking/user_form.html', {
        'form': form,
        'title': 'Nuevo Usuario',
        'is_edit': False
    })


@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    """Edita un usuario existente"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    user = get_object_or_404(User, pk=pk)
    
    # No permitir editar superusuarios
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para editar este usuario.')
        return redirect('user-list')
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            
            # Cambiar contraseña si se proporcionó
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password and confirm_password:
                if new_password == confirm_password:
                    if len(new_password) >= 8:
                        user.set_password(new_password)
                        user.save()
                        messages.success(request, f'Usuario {user.username} y contraseña actualizados exitosamente.')
                    else:
                        messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
                        return render(request, 'parking/user_form.html', {
                            'form': form,
                            'user_obj': user,
                            'title': 'Editar Usuario',
                            'is_edit': True
                        })
                else:
                    messages.error(request, 'Las contraseñas no coinciden.')
                    return render(request, 'parking/user_form.html', {
                        'form': form,
                        'user_obj': user,
                        'title': 'Editar Usuario',
                        'is_edit': True
                    })
            else:
                messages.success(request, f'Usuario {user.username} actualizado exitosamente.')
            
            return redirect('user-list')
    else:
        form = UserEditForm(instance=user)
    
    return render(request, 'parking/user_form.html', {
        'form': form,
        'user_obj': user,
        'title': 'Editar Usuario',
        'is_edit': True
    })


@login_required
@user_passes_test(is_admin)
def user_delete(request, pk):
    """Desactiva un usuario"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    user = get_object_or_404(User, pk=pk)
    
    # No permitir eliminar superusuarios
    if user.is_superuser:
        messages.error(request, 'No se puede eliminar un superusuario.')
        return redirect('user-list')
    
    # No permitir eliminarse a sí mismo
    if user == request.user:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('user-list')
    
    if request.method == 'POST':
        user.is_active = False
        user.save()
        messages.success(request, f'Usuario {user.username} desactivado exitosamente.')
        return redirect('user-list')
    
    return render(request, 'parking/user_confirm_delete.html', {'user_obj': user})


@login_required
@user_passes_test(is_admin)
def user_toggle_status(request, pk):
    """Activa o desactiva un usuario"""
    if not request.current_parking_lot:
        messages.error(request, 'No tienes un parqueadero asignado.')
        return redirect('login')
    
    user = get_object_or_404(User, pk=pk)
    
    # No permitir cambiar estado de superusuarios
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para cambiar el estado de este usuario.')
        return redirect('user-list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activado' if user.is_active else 'desactivado'
    messages.success(request, f'Usuario {user.username} {status} exitosamente.')
    
    return redirect('user-list')
