from django import forms
from django.contrib.auth.models import User
from .models import ParkingTicket, ParkingLot, VehicleCategory


class ParkingTicketForm(forms.ModelForm):
    class Meta:
        model = ParkingTicket
        fields = ['category', 'placa', 'color', 'marca', 'cascos']
        labels = {
            'category': 'Categoría',
            'placa': 'Placa',
            'color': 'Color',
            'marca': 'Marca',
            'cascos': 'Número de cascos',
        }
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'uppercase'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer color, marca y cascos opcionales
        self.fields['color'].required = False
        self.fields['marca'].required = False
        self.fields['cascos'].required = False

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        cascos = cleaned_data.get('cascos')

        # Si es categoría MOTOS, validar cascos
        if category and category.name.upper() == 'MOTOS':
            if cascos is None:
                self.add_error('cascos', 'El número de cascos es obligatorio para motos')
        
        return cleaned_data


class ParkingLotForm(forms.ModelForm):
    class Meta:
        model = ParkingLot
        fields = ['empresa', 'nit', 'telefono', 'direccion']
        labels = {
            'empresa': 'Nombre de la empresa',
            'nit': 'NIT',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = VehicleCategory
        fields = ['name', 'first_hour_rate', 'additional_hour_rate', 'is_monthly', 'monthly_rate']
        labels = {
            'name': 'Nombre',
            'first_hour_rate': 'Tarifa primera hora',
            'additional_hour_rate': 'Tarifa hora adicional',
            'is_monthly': '¿Es mensual?',
            'monthly_rate': 'Tarifa mensual',
        }
        widgets = {
            'first_hour_rate': forms.NumberInput(attrs={'step': '0.01'}),
            'additional_hour_rate': forms.NumberInput(attrs={'step': '0.01'}),
            'monthly_rate': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.parking_lot = kwargs.pop('parking_lot', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.upper()  # Convertir a mayúsculas
            
            # Verificar duplicados solo si estamos creando (no editando)
            if self.parking_lot and not self.instance.pk:
                if VehicleCategory.objects.filter(parking_lot=self.parking_lot, name=name).exists():
                    raise forms.ValidationError(f'Ya existe una categoría con el nombre "{name}" en este parqueadero.')
            
            # Si estamos editando, verificar que no haya otro con el mismo nombre
            elif self.instance.pk and self.parking_lot:
                if VehicleCategory.objects.filter(parking_lot=self.parking_lot, name=name).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError(f'Ya existe otra categoría con el nombre "{name}" en este parqueadero.')
        
        return name

    def clean(self):
        cleaned_data = super().clean()
        is_monthly = cleaned_data.get('is_monthly')
        monthly_rate = cleaned_data.get('monthly_rate')

        # Validar que si es mensual, se especifique una tarifa mensual
        if is_monthly and (monthly_rate is None or monthly_rate <= 0):
            self.add_error('monthly_rate', 'Debe especificar una tarifa mensual válida para una categoría mensual.')
        
        return cleaned_data



class ParkingLotCreateForm(forms.Form):
    """Formulario para crear un nuevo parqueadero"""
    empresa = forms.CharField(
        max_length=255,
        label='Nombre del Parqueadero',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: Parqueadero Central'})
    )
    nit = forms.CharField(
        max_length=20,
        required=False,
        label='NIT',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: 900123456-7'})
    )
    telefono = forms.CharField(
        max_length=20,
        label='Teléfono',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: +57 300 123 4567'})
    )
    direccion = forms.CharField(
        max_length=200,
        label='Dirección',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: Calle 123 #45-67'})
    )
    email = forms.EmailField(
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'correo@ejemplo.com'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Contraseña segura'})
    )
    password_confirm = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Repita la contraseña'})
    )
    subscription_plan = forms.ModelChoiceField(
        queryset=None,
        label='Plan de Suscripción',
        widget=forms.Select(attrs={'class': 'form-input', 'onchange': 'updatePlanInfo(this)'})
    )
    subscription_start = forms.DateField(
        required=False,
        label='Inicio de Suscripción',
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        help_text='Dejar en blanco para usar la fecha actual'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import SubscriptionPlan
        self.fields['subscription_plan'].queryset = SubscriptionPlan.objects.filter(is_active=True)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('Las contraseñas no coinciden.')

        return cleaned_data


class ParkingLotEditForm(forms.ModelForm):
    """Formulario para editar un parqueadero existente"""
    email = forms.EmailField(
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )

    class Meta:
        model = ParkingLot
        fields = ['empresa', 'nit', 'telefono', 'direccion', 'is_active',
                 'subscription_plan', 'plan_type', 'subscription_start', 'subscription_end', 'payment_status']
        labels = {
            'empresa': 'Nombre del Parqueadero',
            'nit': 'NIT',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
            'is_active': 'Activo',
            'subscription_plan': 'Plan de Suscripción',
            'plan_type': 'Tipo de Plan',
            'subscription_start': 'Inicio de Suscripción',
            'subscription_end': 'Fin de Suscripción',
        }
        widgets = {
            'empresa': forms.TextInput(attrs={'class': 'form-input'}),
            'nit': forms.TextInput(attrs={'class': 'form-input'}),
            'telefono': forms.TextInput(attrs={'class': 'form-input'}),
            'direccion': forms.TextInput(attrs={'class': 'form-input'}),
            'subscription_start': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'subscription_end': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
