from django.db import models
from django.conf import settings
from vendor.models import Vehicle
from django.utils import timezone
from mainapp.models import Booking
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import random
import string
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime

class DriverAuth(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # Will store hashed password
    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token_created_at = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    session_token = models.CharField(max_length=100, blank=True, null=True)
    session_expires = models.DateTimeField(null=True, blank=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def generate_verification_token(self):
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.email_verification_token = token
        self.save()
        return token

    def generate_password_reset_token(self):
        token = ''.join(random.choices(string.digits, k=6))
        self.password_reset_token = token
        self.password_reset_token_created_at = timezone.now()
        self.save()
        return token

    def create_session(self):
        # Create a new session token
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        self.session_token = token
        # Set session expiry to 24 hours from now
        self.session_expires = timezone.now() + timezone.timedelta(hours=24)
        self.save()
        return token

    def is_session_valid(self, token):
        return (
            self.session_token == token and 
            self.session_expires and 
            self.session_expires > timezone.now()
        )

    def __str__(self):
        return self.email

class Driver(models.Model):
    STATUS_CHOICES = (
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended')
    )
    
    DRIVING_SKILLS = (
        ('car', 'Car'),
        ('bike', 'Bike'),
        ('both', 'Both')
    )

    auth = models.OneToOneField(
        DriverAuth, 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    address = models.TextField(default='', blank=True)
    city = models.CharField(max_length=100, default='', blank=True)
    license_number = models.CharField(max_length=50, unique=True)
    driving_experience = models.IntegerField(default=0)
    driving_skill = models.CharField(
        max_length=10, 
        choices=DRIVING_SKILLS,
        default='car'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending_approval'
    )
    profile_photo = models.ImageField(upload_to='driver_photos/', null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_drivers'
    )
    blockchain_tx_hash = models.CharField(max_length=66, null=True, blank=True)  # Ethereum transaction hash is 66 characters
    blockchain_verified = models.BooleanField(default=False)  # New field to track blockchain verification status
    availability_status = models.CharField(
        max_length=20,
        choices=[
            ('available', 'Available'),
            ('unavailable', 'Unavailable')
        ],
        default='available'
    )

    def __str__(self):
        return self.full_name

    def send_approval_email(self):
        subject = 'Driver Application Approved'
        html_message = render_to_string('drivers/email/approval.html', {'driver': self})
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            'from@example.com',
            [self.auth.email],
            html_message=html_message
        )

    def send_rejection_email(self, reason=''):
        subject = 'Driver Application Status'
        html_message = render_to_string('drivers/email/rejection.html', {
            'driver': self,
            'reason': reason
        })
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            'from@example.com',
            [self.auth.email],
            html_message=html_message
        )

    def verify_on_blockchain(self):
        """
        Verify the driver's status on the blockchain
        """
        try:
            blockchain = DriverBlockchain()
            driver_data = {
                'license_number': self.license_number,
                'full_name': self.full_name,
                'dob': self.created_at.strftime('%Y-%m-%d') if hasattr(self, 'created_at') else datetime.now().strftime('%Y-%m-%d')
            }
            is_verified = blockchain.verify_driver(str(self.id), driver_data)
            if is_verified != self.blockchain_verified:
                self.blockchain_verified = is_verified
                self.save(update_fields=['blockchain_verified'])
            return is_verified
        except Exception as e:
            return False

class DriverApplicationLog(models.Model):
    ACTION_CHOICES = (
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('document_verify', 'Document Verified'),
    )
    
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE)
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver.full_name} - {self.get_action_display()} - {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']

class DriverBooking(models.Model):
    BOOKING_TYPE_CHOICES = [
        ('specific_date', 'Single Day Booking'),
        ('point_to_point', 'Point to Point Service'),
        ('with_vehicle', 'Booking with Driver Vehicle')
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed')
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ]

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='driver_bookings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPE_CHOICES, default='specific_date')
    
    # Fields for specific date booking (single day)
    booking_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # Fields for multi-day bookings (with vehicle only)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Fields for point to point service
    pickup_location = models.CharField(max_length=255, null=True, blank=True)
    drop_location = models.CharField(max_length=255, null=True, blank=True)
    service_date = models.DateField(null=True, blank=True)
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    drop_latitude = models.FloatField(null=True, blank=True)
    drop_longitude = models.FloatField(null=True, blank=True)
    
    # Fields for booking with driver vehicle
    vehicle = models.ForeignKey('vendor.Vehicle', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Common fields
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'driver_booking'

    def __str__(self):
        return f"Booking {self.id} - {self.driver.full_name} by {self.user.username}"

    def send_confirmation_email(self):
        try:
            subject = 'Driver Booking Confirmation'
            html_message = render_to_string('drivers/email/booking_confirmation.html', {
                'booking': self,
                'driver': self.driver,
                'user': self.user
            })
            
            send_mail(
                subject=subject,
                message=strip_tags(html_message),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user.email],
                html_message=html_message,
                fail_silently=True
            )
        except Exception as e:
            print(f"Error sending confirmation email: {str(e)}")

    def can_start_trip(self):
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        if self.booking_type == 'specific_date':
            return (
                self.status == 'confirmed' and 
                self.payment_status == 'paid' and 
                current_date == self.booking_date and
                current_time >= self.start_time and
                current_time <= self.end_time and
                not hasattr(self, 'trip')
            )
        elif self.booking_type == 'point_to_point':
            return (
                self.status == 'confirmed' and 
                self.payment_status == 'paid' and 
                current_date == self.service_date and
                not hasattr(self, 'trip')
            )
        else:  # with_vehicle
            return (
                self.status == 'confirmed' and 
                self.payment_status == 'paid' and 
                now >= self.start_date and 
                now <= self.end_date and
                not hasattr(self, 'trip') and
                self.vehicle is not None
            )

    def can_end_trip(self):
        if not hasattr(self, 'trip'):
            return False
        now = timezone.now()
        return self.trip.status == 'started'

    def get_booking_details(self):
        if self.booking_type == 'specific_date':
            return {
                'type': 'Single Day Booking',
                'date': self.booking_date,
                'time': f"{self.start_time} to {self.end_time}"
            }
        elif self.booking_type == 'point_to_point':
            return {
                'type': 'Point to Point Service',
                'from': self.pickup_location,
                'to': self.drop_location,
                'date': self.service_date
            }
        else:
            return {
                'type': 'Booking with Driver Vehicle',
                'vehicle': self.vehicle.model if self.vehicle else 'Not assigned',
                'duration': f"{self.start_date} to {self.end_date}"
            }

    def trip(self):
        return DriverTrip.objects.filter(booking=self).first()

class DriverReview(models.Model):
    driver_booking = models.ForeignKey(DriverBooking, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['driver_booking', 'created_by']

class DriverVehicleAssignment(models.Model):
    driver = models.ForeignKey(
        Driver, 
        on_delete=models.CASCADE,
        related_name='vehicle_assignments'
    )
    vehicle = models.ForeignKey(
        Vehicle, 
        on_delete=models.CASCADE,
        related_name='driver_assignments'
    )
    is_active = models.BooleanField(default=True)
    assigned_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    assignment_notes = models.TextField(blank=True)

    class Meta:
        unique_together = [['driver', 'vehicle', 'is_active']]

def driver_document_path(instance, filename):
    # Generate path: documents/driver_<id>/<document_type>/<filename>
    return f'documents/driver_{instance.driver.id}/{instance.document_type}/{filename}'

class DriverDocument(models.Model):
    DOCUMENT_TYPES = (
        ('license', 'Driver License'),
        ('identity', 'Identity Proof'),
        ('address', 'Address Proof'),
    )
    
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to=driver_document_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['driver', 'document_type']
    
    def __str__(self):
        return f"{self.driver.full_name} - {self.get_document_type_display()}"

class DriverSchedule(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [['driver', 'date']]

class DriverTrip(models.Model):
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    )

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips')
    booking = models.ForeignKey('mainapp.Booking', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    distance_covered = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    customer_rating = models.IntegerField(null=True, blank=True)
    customer_feedback = models.TextField(blank=True)

    def __str__(self):
        return f"Trip {self.id} - {self.driver.full_name}"