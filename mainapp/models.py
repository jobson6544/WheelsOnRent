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
from .constants import PLATFORM_FEE_PERCENTAGE  # Add this import

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

    # Add a new field to track authentication method
    AUTH_CHOICES = (
        ('email', 'Email'),
        ('google', 'Google'),
    )
    auth_method = models.CharField(max_length=10, choices=AUTH_CHOICES, default='email')

    def _str_(self):
        return self.email
        
    def save(self, *args, **kwargs):
        if self.auth_method == 'google':
            self.is_email_verified = True
            self.is_active = True
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

    def has_complete_profile(self):
        """Check if user has completed their profile"""
        try:
            return self.profile.is_complete
        except UserProfile.DoesNotExist:
            return False




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



from vendor.models import Vehicle  # Import Vehicle from vendor app

class Booking(models.Model):
    # Add platform fee constant
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('picked_up', 'Picked Up'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed')
    ]

    booking_id = models.AutoField(primary_key=True)  # This replaces the default 'id' field
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle = models.ForeignKey('vendor.Vehicle', on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_status = models.CharField(max_length=20, choices=[
        ('not_refunded', 'Not Refunded'),
        ('refunded', 'Refunded'),
        ('failed', 'Refund Failed'),
    ], default='not_refunded')
    # Add field for tracking rental extensions
    has_been_extended = models.BooleanField(default=False)
    extension_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)

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
        
    def check_extension_availability(self, new_end_date):
        """Check if the vehicle is available for extension until the new end date"""
        if new_end_date <= self.end_date:
            return False
        
        # Check if there are any other bookings that would overlap with the extended period
        overlapping_bookings = Booking.objects.filter(
            vehicle=self.vehicle,
            status__in=['confirmed', 'pending'],
            start_date__lt=new_end_date,
            end_date__gt=self.end_date
        ).exclude(booking_id=self.booking_id)
        
        return not overlapping_bookings.exists()
    
    def calculate_extension_amount(self, new_end_date):
        """Calculate the additional amount for extending the booking"""
        if new_end_date <= self.end_date:
            return 0
        
        # Calculate days difference
        additional_days = (new_end_date - self.end_date).days
        if additional_days <= 0:
            return 0
        
        # Calculate the amount based on the daily rate
        daily_rate = self.vehicle.rental_rate
        extension_amount = additional_days * daily_rate
        
        return extension_amount
    
    def extend_booking(self, new_end_date, payment_intent_id=None):
        """Extend the booking to the new end date"""
        if not self.check_extension_availability(new_end_date):
            return False
        
        old_end_date = self.end_date
        extension_amount = self.calculate_extension_amount(new_end_date)
        
        # Update booking
        self.end_date = new_end_date
        self.has_been_extended = True
        self.total_amount += extension_amount
        
        if payment_intent_id:
            self.extension_payment_intent_id = payment_intent_id
            
        self.save()
        
        # Create extension record
        BookingExtension.objects.create(
            booking=self,
            original_end_date=old_end_date,
            new_end_date=new_end_date,
            extension_amount=extension_amount,
            payment_intent_id=payment_intent_id
        )
        
        return True

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

    def get_status_display_class(self):
        """Return Bootstrap class based on status"""
        status_classes = {
            'pending': 'warning',
            'confirmed': 'primary',
            'picked_up': 'info',
            'returned': 'success',
            'cancelled': 'danger',
            'completed': 'success'
        }
        return status_classes.get(self.status, 'secondary')

    def can_be_cancelled(self):
        """Check if booking can be cancelled"""
        return self.status in ['pending', 'confirmed']

    def can_be_picked_up(self):
        """Check if vehicle can be picked up"""
        return self.status == 'confirmed' and self.start_date <= timezone.now()

    def can_be_returned(self):
        """Check if vehicle can be returned"""
        return self.status == 'picked_up'

    def update_status(self, new_status, user=None):
        """Update booking status with logging"""
        if new_status in dict(self.STATUS_CHOICES):
            old_status = self.status
            self.status = new_status
            self.save()
            
            # Log status change
            BookingStatusLog.objects.create(
                booking=self,
                old_status=old_status,
                new_status=new_status,
                changed_by=user
            )

            # Send appropriate notifications
            self.send_status_notification()
            
            return True
        return False

    def send_status_notification(self):
        """Send notifications based on status changes"""
        templates = {
            'confirmed': 'emails/booking_confirmed.html',
            'picked_up': 'emails/vehicle_picked_up.html',
            'returned': 'emails/vehicle_returned.html',
            'cancelled': 'emails/booking_cancelled.html',
            'completed': 'emails/booking_completed.html'
        }
        
        if self.status in templates:
            context = {
                'booking': self,
                'customer_name': self.user.get_full_name()
            }
            send_status_email(self.user.email, self.status, context)

    def process_early_return(self):
        """Process early return of the vehicle"""
        if self.status != 'picked_up':
            return False, "This booking is not in picked up status"
        
        # Calculate unused days
        current_time = timezone.now()
        if current_time >= self.end_date:
            # No unused days if returning after end date
            unused_days = 0
        else:
            # Calculate unused days (round down)
            unused_days = (self.end_date - current_time).days
        
        # Update booking status
        self.status = 'returned'
        self.save()
        
        return True, unused_days

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

class BookingExtension(models.Model):
    """Model to track booking extensions"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='extensions')
    original_end_date = models.DateTimeField()
    new_end_date = models.DateTimeField()
    extension_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Extension for Booking {self.booking.booking_id}"

class AccidentReport(models.Model):
    """Model to store accident reports"""
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('severe', 'Severe'),
    ]
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='accident_reports')
    report_date = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_emergency = models.BooleanField(default=False)
    photos = models.ImageField(upload_to='accident_reports/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('reported', 'Reported'),
        ('processing', 'Processing'),
        ('resolved', 'Resolved'),
    ], default='reported')
    
    def __str__(self):
        return f"Accident Report {self.id} for Booking {self.booking.booking_id}"

class LocationShare(models.Model):
    """Model to store location sharing data"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='shared_locations')
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)  # Changed from auto_now_add to allow custom timestamps
    is_active = models.BooleanField(default=True)
    is_live_tracking = models.BooleanField(default=False)  # Indicates if this is from live tracking
    accuracy = models.FloatField(null=True, blank=True)  # GPS accuracy in meters, if available
    
    def __str__(self):
        return f"Location for Booking {self.booking.booking_id} at {self.timestamp}"
