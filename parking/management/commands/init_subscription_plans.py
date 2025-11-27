from django.core.management.base import BaseCommand
from parking.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Inicializa los planes de suscripción predeterminados'

    def handle(self, *args, **kwargs):
        plans = [
            {
                'name': 'Plan Mensual',
                'plan_type': 'MENSUAL',
                'price': 50000,
                'duration_days': 30,
                'description': 'Suscripción mensual con renovación cada 30 días'
            },
            {
                'name': 'Plan Trimestral',
                'plan_type': 'TRIMESTRAL',
                'price': 135000,
                'duration_days': 90,
                'description': 'Suscripción trimestral con 10% de descuento'
            },
            {
                'name': 'Plan Semestral',
                'plan_type': 'SEMESTRAL',
                'price': 255000,
                'duration_days': 180,
                'description': 'Suscripción semestral con 15% de descuento'
            },
            {
                'name': 'Plan Anual',
                'plan_type': 'ANUAL',
                'price': 480000,
                'duration_days': 365,
                'description': 'Suscripción anual con 20% de descuento'
            },
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.get_or_create(
                plan_type=plan_data['plan_type'],
                defaults=plan_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Plan creado: {plan.name} - ${plan.price}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'○ Plan ya existe: {plan.name}')
                )

        self.stdout.write(self.style.SUCCESS('\n✅ Planes de suscripción inicializados correctamente'))
