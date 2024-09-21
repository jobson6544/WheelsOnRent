from django.core.management.base import BaseCommand
from vendor.models import Vehicle, RentalPriceHistory
from django.utils import timezone
import random
from datetime import timedelta
from decimal import Decimal

class Command(BaseCommand):
    help = 'Populates rental price history with dummy data'

    def handle(self, *args, **kwargs):
        vehicles = Vehicle.objects.all()
        start_date = timezone.now().date() - timedelta(days=365)
        
        for vehicle in vehicles:
            current_date = start_date
            while current_date <= timezone.now().date():
                season = self.get_season(current_date)
                price = vehicle.rental_rate * Decimal(str(random.uniform(0.8, 1.2)))  # Random fluctuation
                units_rented = random.randint(0, 5)
                
                RentalPriceHistory.objects.create(
                    vehicle=vehicle,
                    date=current_date,
                    price=price,
                    units_rented=units_rented,
                    season=season,
                    day_of_week=current_date.weekday(),
                    is_holiday=random.choice([True, False]),
                    weather_condition=random.choice(['sunny', 'rainy', 'cloudy', 'snowy']),
                    competitor_price=price * Decimal(str(random.uniform(0.9, 1.1)))
                )
                
                current_date += timedelta(days=1)
        
        self.stdout.write(self.style.SUCCESS('Successfully populated rental price history'))

    def get_season(self, date):
        month = date.month
        if 3 <= month <= 5:
            return 'spring'
        elif 6 <= month <= 8:
            return 'summer'
        elif 9 <= month <= 11:
            return 'fall'
        else:
            return 'winter'
