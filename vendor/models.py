from django.db import models
from django.conf import settings
from django.utils import timezone

class Vendor(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    vendor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=10)
    contact_number = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.business_name

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
    status = models.IntegerField(default=1)  # 1 for active, 0 for deleted
    fuel_type = models.CharField(max_length=20, choices=FUEL_CHOICES)
    engine_number = models.CharField(max_length=50)
    chassis_number = models.CharField(max_length=50)
    image = models.ImageField(upload_to='vehicle_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.model} - {self.registration.registration_number}"

    def get_insurance(self):
        try:
            return self.insurance
        except Insurance.DoesNotExist:
            return None

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