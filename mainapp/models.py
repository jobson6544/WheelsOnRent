from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
        ('vendor', 'Vendor'),
    )
    
    fullname = models.CharField(max_length=255)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_staff = models.BooleanField(default=False)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    # Use email as the unique identifier instead of username
    email = models.EmailField(unique=True)
    is_first_login = models.BooleanField(default=True)

    # If you want to use email for login instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'fullname']

    def _str_(self):
        return self.email
        
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
    is_complete = models.BooleanField(default=False)  # Added this line

    def __str__(self):
        return self.user.username

class Vendor(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    vendor_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=10)
    contact_number = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.business_name