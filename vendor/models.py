from django.db import models
from django.conf import settings
from django.utils import timezone
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from decimal import Decimal
import holidays
import requests
from datetime import datetime
import googlemaps
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import random
import string
import joblib
from django.db.models import Avg

class Vendor(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    vendor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255)
    full_address = models.TextField()
    contact_number = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='vendor_profiles/', null=True, blank=True)
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token_created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if not self.latitude or not self.longitude:
            self.geocode_address()
        super().save(*args, **kwargs)

    def geocode_address(self):
        gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        try:
            geocode_result = gmaps.geocode(self.full_address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                self.latitude = location['lat']
                self.longitude = location['lng']
        except Exception as e:
            print(f"Geocoding error: {e}")

    def get_full_address(self):
        return f"{self.address}, {self.city}, {self.state}, {self.zip_code}"

    def generate_password_reset_token(self):
        token = ''.join(random.choices(string.digits, k=6))
        self.password_reset_token = token
        self.password_reset_token_created_at = timezone.now()
        self.save()
        return token

    def is_password_reset_token_valid(self):
        if not self.password_reset_token or not self.password_reset_token_created_at:
            return False
        return timezone.now() - self.password_reset_token_created_at < timezone.timedelta(minutes=15)

    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return None  # or return a URL to a default image

    def get_all_feedback(self):
        """Get all feedback for this vendor's vehicles"""
        return Feedback.objects.filter(booking__vehicle__vendor=self)

    def get_average_rating(self):
        """Get the average rating for this vendor"""
        feedbacks = self.get_all_feedback()
        if feedbacks.exists():
            return feedbacks.aggregate(Avg('rating'))['rating__avg']
        return 0

class VehicleType(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.category_name

class VehicleCompany(models.Model):
    sub_category_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('category', 'company_name')

    def __str__(self):
        return f"{self.company_name} ({self.category})"

class Model(models.Model):
    model_id = models.AutoField(primary_key=True)
    sub_category = models.ForeignKey(VehicleCompany, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=255)
    model_year = models.IntegerField()  # Using IntegerField as Django doesn't have a YEAR field
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.model_name} ({self.model_year})"

class Registration(models.Model):
    registration_id = models.AutoField(primary_key=True)
    registration_number = models.CharField(max_length=255)  # Ensure unique=True is removed
    registration_date = models.DateField()
    registration_end_date = models.DateField()

    def __str__(self):
        return self.registration_number

class Features(models.Model):
    feature_id = models.AutoField(primary_key=True)
    feature_name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.feature_name

class Vehicle(models.Model):
    STATUS_CHOICES = [
        (1, 'Available'),
        (2, 'Rented'),
        (3, 'Maintenance'),
        (4, 'Delivered'),
    ]

    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
        ('cng', 'CNG'),
        ('lpg', 'LPG'),
    ]

    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='vehicles')
    model = models.ForeignKey('Model', on_delete=models.CASCADE)
    registration = models.OneToOneField('Registration', on_delete=models.CASCADE)
    insurance = models.OneToOneField('Insurance', on_delete=models.CASCADE, null=True, blank=True, related_name='insured_vehicle')
    features = models.ManyToManyField('Features')
    availability = models.BooleanField(default=True)
    rental_rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)
    fuel_type = models.CharField(max_length=20, choices=FUEL_CHOICES)
    engine_number = models.CharField(max_length=50)
    chassis_number = models.CharField(max_length=50)
    image = models.ImageField(upload_to='vehicle_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    mileage = models.IntegerField(default=0, help_text="Current mileage of the vehicle")

    # New fields for price prediction
    year = models.IntegerField(default=datetime.now().year)
    seating_capacity = models.IntegerField(default=5)
    transmission = models.CharField(max_length=20, choices=[('manual', 'Manual'), ('automatic', 'Automatic')], default='manual')
    air_conditioning = models.BooleanField(default=True)
    fuel_efficiency = models.FloatField(default=0.0)  # km per liter

    # Temporary field for predicted price
    predicted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.model} - {self.registration.registration_number}"

    def get_insurance(self):
        try:
            return self.insurance
        except Insurance.DoesNotExist:
            return None

    def get_suggested_price(self):
        history = self.price_history.order_by('-date')[:90]  # Last 90 days
        if len(history) < 30:
            return self.rental_rate

        X = np.array([[
            h.date.toordinal(),
            h.units_rented,
            {'summer': 0, 'fall': 1, 'winter': 2, 'spring': 3}[h.season],
            self.model.model_year,
            len(self.features.all()),
            h.day_of_week,
            int(h.is_holiday),
            {'sunny': 0, 'rainy': 1, 'cloudy': 2, 'snowy': 3}.get(h.weather_condition, 0),
            float(h.competitor_price) if h.competitor_price else 0,
            self.model.sub_category.category.category_id,
            {'petrol': 0, 'diesel': 1, 'electric': 2, 'hybrid': 3, 'cng': 4, 'lpg': 5}.get(self.fuel_type, 0),
            self.mileage,
        ] for h in history])
        y = np.array([float(h.price) for h in history])

        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        tomorrow = timezone.now().date() + timezone.timedelta(days=1)
        season = self.get_season(tomorrow)
        is_holiday = self.is_holiday(tomorrow)
        weather_condition = self.get_weather_condition()

        prediction = model.predict([[
            tomorrow.toordinal(),
            0,  # units_rented (unknown for future)
            {'summer': 0, 'fall': 1, 'winter': 2, 'spring': 3}[season],
            self.model.model_year,
            len(self.features.all()),
            tomorrow.weekday(),
            int(is_holiday),
            weather_condition,
            float(self.rental_rate),  # using current rate as competitor price
            self.model.sub_category.category.category_id,
            {'petrol': 0, 'diesel': 1, 'electric': 2, 'hybrid': 3, 'cng': 4, 'lpg': 5}.get(self.fuel_type, 0),
            self.mileage,
        ]])

        base_price = prediction[0]
        
        # Add platform fee to suggested price
        platform_fee_multiplier = 1 + (Booking.PLATFORM_FEE_PERCENTAGE / 100)
        adjusted_price = base_price * platform_fee_multiplier
        
        # Weather adjustments
        if weather_condition == 1:  # Rainy
            adjusted_price *= 1.1
        elif weather_condition == 3:  # Snowy
            adjusted_price *= 1.2
        
        return Decimal(str(round(float(adjusted_price), 2)))

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

    def is_holiday(self, date):
        country_holidays = holidays.IN()  # Use 'IN' for India
        return date in country_holidays

    def get_weather_condition(self):
        api_key = settings.OPENWEATHERMAP_API_KEY
        city = self.vendor.city if hasattr(self, 'vendor') and self.vendor else "London"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
        
        print(f"Fetching weather for city: {city}")
        print(f"API URL: {url}")
        print(f"API Key used: {api_key}")
        
        try:
            response = requests.get(url)
            print(f"API Response status code: {response.status_code}")
            print(f"API Response content: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                weather_main = data['weather'][0]['main'].lower()
                if 'rain' in weather_main:
                    return 1  # Rainy
                elif 'snow' in weather_main:
                    return 3  # Snowy
                elif 'cloud' in weather_main:
                    return 2  # Cloudy
                else:
                    return 0  # Sunny/Clear
            else:
                print(f"Error fetching weather data: {response.status_code}")
                return 0  # Default to Sunny/Clear if API call fails
        except Exception as e:
            print(f"Exception in get_weather_condition: {e}")
            return 0  # Default to Sunny/Clear if any exception occurs

    def get_bookings(self):
        return self.bookings.all()  # Assuming you've set up a related_name in the Booking model

    def mark_as_rented(self):
        self.status = 2  # Use the integer value for 'Rented'
        self.save()

    def mark_as_returned(self):
        self.status = 1  # Use the integer value for 'Available'
        self.save()

    def mark_as_delivered(self):
        self.status = 4  # Use the integer value for 'Delivered'
        self.save()

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, 'Unknown')

    def predict_price(self):
        # Load the trained model
        model = joblib.load('trained_rental_price_model.joblib')
        
        # Prepare the input features
        features = np.array([[
            self.year,
            self.mileage,
            self.seating_capacity,
            1 if self.transmission == 'automatic' else 0,
            1 if self.air_conditioning else 0,
            self.fuel_efficiency,
            self.model.model_year,
            len(self.features.all()),
            {'petrol': 0, 'diesel': 1, 'electric': 2, 'hybrid': 3, 'cng': 4, 'lpg': 5}.get(self.fuel_type, 0),
            # Add additional features to match the 20 expected by the model
            self.rental_rate,  # Current rental rate
            self.status,
            self.created_at.year,
            self.created_at.month,
            self.created_at.day,
            self.updated_at.year,
            self.updated_at.month,
            self.updated_at.day,
            self.vendor.vendor_id,
            self.model.model_id,
            self.registration.registration_id
        ]])
        
        # Make prediction
        predicted_price = model.predict(features)[0]
        
        # Add platform fee to predicted price
        platform_fee_multiplier = 1 + (Booking.PLATFORM_FEE_PERCENTAGE / 100)
        adjusted_price = predicted_price * platform_fee_multiplier
        
        return round(adjusted_price, 2)

class Image(models.Model):
    image_id = models.AutoField(primary_key=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='vehicle_images/')

    def __str__(self):
        return f"Image for {self.vehicle}"

class Insurance(models.Model):
    COVERAGE_CHOICES = [
        ('third_party', 'Third Party'),
        ('comprehensive', 'Comprehensive'),
        ('zero_dep', 'Zero Depreciation'),
    ]

    vehicle = models.OneToOneField('Vehicle', on_delete=models.CASCADE, related_name='vehicle_insurance')
    policy_number = models.CharField(max_length=50, unique=True)
    policy_provider = models.CharField(max_length=100)
    coverage_type = models.CharField(max_length=20, choices=COVERAGE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    road_tax_details = models.CharField(max_length=255)
    fitness_expiry_date = models.DateField()
    puc_expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Insurance for {self.vehicle} (Policy: {self.policy_number})"

    def is_fitness_valid(self):
        return self.fitness_expiry_date > timezone.now().date()

    def is_puc_valid(self):
        return self.puc_expiry_date > timezone.now().date()

    def is_insurance_valid(self):
        return self.start_date <= timezone.now().date() <= self.end_date

class VehicleDocument(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')
    rc_document = models.FileField(upload_to='documents/rc/', blank=True, null=True)
    insurance_document = models.FileField(upload_to='documents/insurance/', blank=True, null=True)
    puc_document = models.FileField(upload_to='documents/puc/', blank=True, null=True)

    def __str__(self):
        return f"Documents for {self.vehicle}"

class RentalPriceHistory(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='price_history')
    date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    units_rented = models.IntegerField(default=0)
    season = models.CharField(max_length=10, choices=[('summer', 'Summer'), ('fall', 'Fall'), ('winter', 'Winter'), ('spring', 'Spring')])
    day_of_week = models.IntegerField()  # 0 for Monday, 6 for Sunday
    is_holiday = models.BooleanField(default=False)
    weather_condition = models.CharField(max_length=20, default='normal')  # e.g., 'sunny', 'rainy', 'snowy'
    competitor_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.vehicle} - {self.date} - ${self.price}"

class Pickup(models.Model):
    booking = models.OneToOneField('mainapp.Booking', on_delete=models.CASCADE, related_name='pickup')
    qr_code = models.CharField(max_length=50, unique=True)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    pickup_time = models.DateTimeField(null=True, blank=True)

    def generate_qr_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=50))

    def generate_otp(self):
        return ''.join(random.choices(string.digits, k=6))

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        if not self.otp:
            self.otp = self.generate_otp()
        super().save(*args, **kwargs)

class Return(models.Model):
    booking = models.OneToOneField('mainapp.Booking', on_delete=models.CASCADE, related_name='vehicle_return')
    qr_code = models.CharField(max_length=50, unique=True)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    return_time = models.DateTimeField(null=True, blank=True)

    def generate_qr_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=50))

    def generate_otp(self):
        return ''.join(random.choices(string.digits, k=6))

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        if not self.otp:
            self.otp = self.generate_otp()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Return for Booking {self.booking.booking_id}"

class Booking(models.Model):
    # ... existing fields ...

    def send_pickup_email(self):
        subject = 'Vehicle Pickup Information'
        html_message = render_to_string('emails/pickup_info.html', {'booking': self})
        plain_message = strip_tags(html_message)
        send_mail(subject, plain_message, 'from@example.com', [self.user.email], html_message=html_message)

    def send_return_email(self):
        subject = 'Vehicle Return Information'
        html_message = render_to_string('emails/return_info.html', {'booking': self})
        plain_message = strip_tags(html_message)
        send_mail(subject, plain_message, 'from@example.com', [self.user.email], html_message=html_message)

    def send_feedback_email(self):
        subject = 'Feedback Request'
        html_message = render_to_string('emails/feedback_request.html', {'booking': self})
        plain_message = strip_tags(html_message)
        send_mail(subject, plain_message, 'from@example.com', [self.user.email], html_message=html_message)

class Report(models.Model):
    REPORT_TYPES = [
        ('booking', 'Booking Report'),
        ('revenue', 'Revenue Report'),
        ('vehicle', 'Vehicle Report'),
        ('feedback', 'Feedback Report'),
    ]
    
    FILE_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    file_format = models.CharField(max_length=10, choices=FILE_FORMATS)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    generated_file = models.FileField(upload_to='reports/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.created_at.date()}"

