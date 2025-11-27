# -*- coding: utf-8 -*-
"""
Formularios para gestión de usuarios y permisos
"""

from django import forms
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.forms import UserCreationForm


class UserCreateForm(UserCreationForm):
    """Formulario para crear nuevos usuarios"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'usuario@email.com'
        })
    )
    
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'Nombre del usuario'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'Apellido del usuario'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre de usuario',
        widget=forms.TextInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'usuario123'
        })
    )
    
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': '••••••••'
        })
    )
    
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': '••••••••'
        })
    )
    
    role = forms.ChoiceField(
        choices=[
            ('', 'Seleccione un rol'),
            ('admin', 'Administrador'),
            ('cajero', 'Cajero'),
            ('operador', 'Operador'),
        ],
        required=True,
        label='Rol',
        widget=forms.Select(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white'
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label='Usuario activo',
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 text-primary border-2 border-gray-300 rounded focus:ring-2 focus:ring-primary-light'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'role', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Desactivar validaciones de contraseña de Django
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None
    
    def clean_password2(self):
        """Validar solo que las contraseñas coincidan, sin otras validaciones"""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        
        return password2
    
    def _post_clean(self):
        """Sobrescribir para evitar las validaciones de contraseña de Django"""
        super(forms.ModelForm, self)._post_clean()  # Llamar al _post_clean de ModelForm, no de UserCreationForm
    
    def clean_email(self):
        """Validar que el email no esté en uso"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email ya está en uso por otro usuario.')
        return email
    
    def clean_username(self):
        """Validar que el username no esté en uso"""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = self.cleaned_data.get('is_active', True)
        
        if commit:
            user.save()
            
            # Asignar rol/grupo
            role = self.cleaned_data.get('role')
            if role:
                self.assign_role(user, role)
        
        return user
    
    def assign_role(self, user, role):
        """Asigna el rol y permisos correspondientes al usuario"""
        # Limpiar grupos anteriores
        user.groups.clear()
        
        # Crear o obtener el grupo
        group, created = Group.objects.get_or_create(name=role.capitalize())
        
        # Asignar permisos según el rol
        if role == 'admin':
            # Administrador tiene todos los permisos
            permissions = Permission.objects.filter(
                content_type__app_label='parking'
            )
            group.permissions.set(permissions)
            user.is_staff = True
        
        elif role == 'cajero':
            # Cajero puede ver y crear tickets, ver reportes
            permissions = Permission.objects.filter(
                content_type__app_label='parking',
                codename__in=[
                    'add_parkingticket',
                    'view_parkingticket',
                    'change_parkingticket',
                    'view_caja',
                    'add_caja',
                    'change_caja',
                ]
            )
            group.permissions.set(permissions)
            user.is_staff = False
        
        elif role == 'operador':
            # Operador solo puede crear y ver tickets
            permissions = Permission.objects.filter(
                content_type__app_label='parking',
                codename__in=[
                    'add_parkingticket',
                    'view_parkingticket',
                ]
            )
            group.permissions.set(permissions)
            user.is_staff = False
        
        user.groups.add(group)
        user.save()


class UserEditForm(forms.ModelForm):
    """Formulario para editar usuarios existentes"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'usuario@email.com'
        })
    )
    
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'Nombre del usuario'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white',
            'placeholder': 'Apellido del usuario'
        })
    )
    
    role = forms.ChoiceField(
        choices=[
            ('admin', 'Administrador'),
            ('cajero', 'Cajero'),
            ('operador', 'Operador'),
        ],
        required=True,
        label='Rol',
        widget=forms.Select(attrs={
            'class': 'block w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary rounded-xl shadow-sm transition-all bg-white'
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        label='Usuario activo',
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 text-primary border-2 border-gray-300 rounded focus:ring-2 focus:ring-primary-light'
        })
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer el rol actual del usuario
        if self.instance and self.instance.pk:
            user_groups = list(self.instance.groups.values_list('name', flat=True))
            if 'Admin' in user_groups or 'Administrador' in user_groups or self.instance.is_staff:
                self.fields['role'].initial = 'admin'
            elif 'Cajero' in user_groups:
                self.fields['role'].initial = 'cajero'
            elif 'Operador' in user_groups:
                self.fields['role'].initial = 'operador'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            
            # Actualizar rol/grupo
            role = self.cleaned_data.get('role')
            if role:
                self.assign_role(user, role)
        
        return user
    
    def assign_role(self, user, role):
        """Asigna el rol y permisos correspondientes al usuario"""
        # Limpiar grupos anteriores
        user.groups.clear()
        
        # Crear o obtener el grupo
        group, created = Group.objects.get_or_create(name=role.capitalize())
        
        # Asignar permisos según el rol
        if role == 'admin':
            permissions = Permission.objects.filter(
                content_type__app_label='parking'
            )
            group.permissions.set(permissions)
            user.is_staff = True
        
        elif role == 'cajero':
            permissions = Permission.objects.filter(
                content_type__app_label='parking',
                codename__in=[
                    'add_parkingticket',
                    'view_parkingticket',
                    'change_parkingticket',
                    'view_caja',
                    'add_caja',
                    'change_caja',
                ]
            )
            group.permissions.set(permissions)
            user.is_staff = False
        
        elif role == 'operador':
            permissions = Permission.objects.filter(
                content_type__app_label='parking',
                codename__in=[
                    'add_parkingticket',
                    'view_parkingticket',
                ]
            )
            group.permissions.set(permissions)
            user.is_staff = False
        
        user.groups.add(group)
        user.save()
