from django.contrib import admin
from django.apps import apps

# Registrar todos los modelos automáticamente
models = apps.get_models()

for model in models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
