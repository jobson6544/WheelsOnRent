from django.conf import settings
from django.db import models
from vendor.models import Vehicle
from django.contrib.auth.models import AbstractUser
import os

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

    # If you want to use email for login instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    def _str_(self):
        return self.email
        
    def save(self, *args, **kwargs):
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)
        
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
    booking_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
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