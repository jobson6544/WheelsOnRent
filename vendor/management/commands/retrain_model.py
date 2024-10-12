from django.core.management.base import BaseCommand
from vendor.ml_utils import train_model

class Command(BaseCommand):
    help = 'Retrains the ML model for price prediction'

    def handle(self, *args, **options):
        train_model()
        self.stdout.write(self.style.SUCCESS('Successfully retrained the model'))
