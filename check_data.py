import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wheelsonrent.settings")
django.setup()

from vendor.models import RentalPriceHistory

print(RentalPriceHistory.objects.count())
