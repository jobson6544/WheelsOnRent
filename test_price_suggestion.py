import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wheelsonrent.settings")
django.setup()

from vendor.models import Vehicle

def test_price_suggestion():
    vehicle = Vehicle.objects.first()
    if vehicle:
        suggested_price = vehicle.get_suggested_price()
        print(f"Suggested price for {vehicle}: ${suggested_price}")
    else:
        print("No vehicles found in the database.")

if __name__ == "__main__":
    test_price_suggestion()
