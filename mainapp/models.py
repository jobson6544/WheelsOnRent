from django.conf import settings
from django.db import models
from vendor.models import Vehicle
from django.contrib.auth.models import AbstractUser
import os
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
import json  # Add this import at the top of the file
import logging
import random
from django.utils import timezone
import string

logger = logging.getLogger(__name__)

def profile_photo_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/profile_photos/user_<id>/<filename>
    return os.path.join('profile_photos', f'user_{instance.user.id}', filename)

def license_front_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/license_photos/user_<id>/front/<filename>
    return os.path.join('license_photos', f'user_{instance.user.id}', 'front', filename)

def license_back_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/license_photos/user_<id>/back/<filename>
    return os.path.join('license_photos', f'user_{instance.user.id}', 'back', filename)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
        ('vendor', 'Vendor'),
    )
    
    full_name = models.CharField(max_length=255, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_staff = models.BooleanField(default=False)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    # Use email as the unique identifier instead of username
    email = models.EmailField(unique=True)
    is_first_login = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token_created_at = models.DateTimeField(null=True, blank=True)

    # If you want to use email for login instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    def _str_(self):
        return self.email
        
    def save(self, *args, **kwargs):
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)
        
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

# Model for storing additional user details
# class Customer(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     phone = models.CharField(max_length=15)
#     driving_license = models.CharField(max_length=50)
    
#     def __str__(self):
#         return self.user.username


#old name 
# class Profile(models.Model):

# #new name
# class Address(models.Model):
#     ADDRESS_TYPE_CHOICES = (
#         ('home', 'Home'),
#         ('office', 'Office'),
#     )
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='address')
#     flat_house_no = models.CharField(max_length=255, verbose_name="Flat/House No:/Building/Company/Apartment")
#     area_street = models.CharField(max_length=255, verbose_name="Area/Street/Sector/Village")
#     landmark = models.CharField(max_length=255)
#     pincode = models.CharField(max_length=10)
#     town_city = models.CharField(max_length=100, verbose_name="Town/City")
#     state = models.CharField(max_length=100)
#     country = models.CharField(max_length=100)
#     address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='home')
#     is_primary = models.BooleanField(default=False)

#     def _str_(self):
#         return f"{self.user.username}'s Address"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15)
    license_number = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=10)
    is_complete = models.BooleanField(default=False)
    profile_photo = models.ImageField(upload_to=profile_photo_path, null=True, blank=True)
    license_front = models.ImageField(upload_to=license_front_path, null=True, blank=True)
    license_back = models.ImageField(upload_to=license_back_path, null=True, blank=True)

    def __str__(self):
        return self.user.username

# class Vendor(models.Model):
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#     ]

#     vendor_id = models.AutoField(primary_key=True)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     business_name = models.CharField(max_length=255)
#     address = models.TextField(blank=True, null=True)
#     city = models.CharField(max_length=255)
#     state = models.CharField(max_length=255)
#     zip_code = models.CharField(max_length=10)
#     contact_number = models.CharField(max_length=15)
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

#     def __str__(self):
#         return self.business_name

from vendor.models import Vehicle  # Import Vehicle from vendor app

class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)  # This replaces the default 'id' field
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle = models.ForeignKey('vendor.Vehicle', on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ], default='pending')
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_status = models.CharField(max_length=20, choices=[
        ('not_refunded', 'Not Refunded'),
        ('refunded', 'Refunded'),
        ('failed', 'Refund Failed'),
    ], default='not_refunded')

    def __str__(self):
        return f"Booking for {self.vehicle} by {self.user.username}"

    class Meta:
        db_table = 'bookings'

    @classmethod
    def check_availability(cls, vehicle, start_date, end_date):
        logger.info(f"Checking availability for vehicle {vehicle.id} from {start_date} to {end_date}")
        overlapping_bookings = cls.objects.filter(
            vehicle=vehicle,
            status__in=['confirmed', 'pending'],
            start_date__lt=end_date,
            end_date__gt=start_date
        )
        is_available = not overlapping_bookings.exists()
        logger.info(f"Overlapping bookings found: {overlapping_bookings.count()}")
        logger.info(f"Is vehicle available: {is_available}")
        return is_available

    def generate_qr_code(self, qr_type):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        
        booking_data = {
            'booking_id': self.booking_id,
            'customer_id': self.user.id,
            'vehicle_id': self.vehicle.id,
            'type': qr_type,
        }
        if qr_type == 'return':
            booking_data['return_date'] = self.end_date.isoformat()
        
        qr.add_data(json.dumps(booking_data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_file = ContentFile(buffer.getvalue())
        
        return qr_file

    def generate_and_send_qr(self, request):
        pickup_qr = self.generate_qr_code('pickup')
        return_qr = self.generate_qr_code('return')
        
        subject = 'Vehicle Pickup and Return QR Codes'
        html_content = render_to_string('emails/pickup_return_qr.html', {'booking': self})
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [self.user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.attach(f'pickup_qr_{self.booking_id}.png', pickup_qr.read(), 'image/png')
        email.attach(f'return_qr_{self.booking_id}.png', return_qr.read(), 'image/png')
        email.send()

    def send_pickup_email(self):
        subject = 'Vehicle Pickup Confirmation'
        context = {
            'booking': self,
            'customer_name': self.user.get_full_name() or self.user.username,
        }
        html_message = render_to_string('emails/pickup_confirmation.html', context)
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = self.user.email

        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )

    def send_return_email(self):
        subject = 'Vehicle Return Confirmation'
        context = {
            'booking': self,
            'customer_name': self.user.get_full_name() or self.user.username,
        }
        html_message = render_to_string('emails/return_confirmation.html', context)
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = self.user.email

        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )

    def get_vehicle_details(self):
        return {
            'model': self.vehicle.model.model_name,
            'year': self.vehicle.model.model_year,
            'company': self.vehicle.model.sub_category.company_name,
            'type': self.vehicle.model.sub_category.category.category_name,
            'fuel_type': self.vehicle.get_fuel_type_display(),
            'registration_number': self.vehicle.registration.registration_number,
            'image': self.vehicle.image.url if self.vehicle.image else None,
            'image_url': self.vehicle.image_url if hasattr(self.vehicle, 'image_url') else None,
        }

    def get_vendor_details(self):
        return {
            'business_name': self.vehicle.vendor.business_name,
            'contact_number': self.vehicle.vendor.contact_number,
            'full_address': self.vehicle.vendor.full_address,
        }

    def can_submit_feedback(self):
        """Check if feedback can be submitted for this booking"""
        return (
            self.status == 'returned' and 
            not hasattr(self, 'feedback')
        )

class Feedback(models.Model):
    RATING_CHOICES = (
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    )
    
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Feedback for Booking {self.booking.booking_id}"
