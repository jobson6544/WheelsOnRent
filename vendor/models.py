from django.db import models
from django.conf import settings

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
    registration_number = models.CharField(max_length=255, unique=True)
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
    vehicle_id = models.AutoField(primary_key=True)
    model = models.ForeignKey(Model, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='vehicles')
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    features = models.ManyToManyField(Features)
    availability = models.BooleanField(default=True)
    rental_rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.IntegerField(default=1)  # 1 for active, 0 for deleted
    image = models.ImageField(upload_to='vehicle_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.model} - {self.registration.registration_number}"

class Image(models.Model):
    image_id = models.AutoField(primary_key=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='vehicle_images/')

    def __str__(self):
        return f"Image for {self.vehicle}"