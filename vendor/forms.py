from django import forms
from django.contrib.auth.forms import UserCreationForm
from mainapp.models import User
from .models import Vehicle, VehicleDocument, Insurance, Registration, Features, VehicleType, VehicleCompany, Model, Vendor

class VendorUserForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=255, required=True)

    class Meta:
        model = User
        fields = ('username', 'full_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data['full_name']
        user.role = 'vendor'
        if commit:
            user.save()
        return user

class VendorProfileForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['business_name', 'full_address', 'contact_number', 'profile_picture', 'latitude', 'longitude']
        widgets = {
            'profile_picture': forms.FileInput(),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if latitude is None or longitude is None:
            raise forms.ValidationError("Latitude and longitude are required. Please ensure your address is valid.")

        return cleaned_data

class VendorLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class VehicleForm(forms.ModelForm):
    vehicle_type = forms.ModelChoiceField(
        queryset=VehicleType.objects.filter(is_active=True),
        empty_label="Select Vehicle Type"
    )
    vehicle_company = forms.ModelChoiceField(
        queryset=VehicleCompany.objects.none(),
        empty_label="Select Vehicle Company"
    )
    model = forms.ModelChoiceField(
        queryset=Model.objects.none(),
        empty_label="Select Model"
    )
    fuel_type = forms.ChoiceField(choices=Vehicle.FUEL_CHOICES)
    engine_number = forms.CharField(max_length=50)
    chassis_number = forms.CharField(max_length=50)
    rental_rate = forms.DecimalField(max_digits=10, decimal_places=2)
    availability = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    image = forms.ImageField(required=False)

    # Registration fields
    registration_number = forms.CharField(max_length=255)
    registration_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    registration_end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    
    # Insurance fields
    policy_number = forms.CharField(max_length=50)
    policy_provider = forms.CharField(max_length=100)
    coverage_type = forms.ChoiceField(choices=Insurance.COVERAGE_CHOICES)
    insurance_start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    insurance_end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    road_tax_details = forms.CharField(max_length=255)
    fitness_expiry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    puc_expiry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    features = forms.ModelMultipleChoiceField(
        queryset=Features.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    year = forms.IntegerField()
    mileage = forms.IntegerField()
    seating_capacity = forms.IntegerField()
    transmission = forms.ChoiceField(
        choices=[('manual', 'Manual'), ('automatic', 'Automatic')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    air_conditioning = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    fuel_efficiency = forms.FloatField()

    class Meta:
        model = Vehicle
        fields = [
            'vehicle_type', 'vehicle_company', 'model', 'fuel_type', 'engine_number', 
            'chassis_number', 'rental_rate', 'availability', 'image', 'registration_number', 
            'registration_date', 'registration_end_date', 'policy_number', 'policy_provider', 
            'coverage_type', 'insurance_start_date', 'insurance_end_date', 'road_tax_details', 
            'fitness_expiry_date', 'puc_expiry_date', 'features', 'year', 'mileage', 
            'seating_capacity', 'transmission', 'air_conditioning', 'fuel_efficiency'
        ]

    def __init__(self, *args, **kwargs):
        self.vendor = kwargs.pop('vendor', None)
        super().__init__(*args, **kwargs)
        
        if 'vehicle_type' in self.data:
            try:
                vehicle_type_id = int(self.data.get('vehicle_type'))
                self.fields['vehicle_company'].queryset = VehicleCompany.objects.filter(category_id=vehicle_type_id, is_active=True)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['vehicle_company'].queryset = self.instance.model.sub_category.category.vehiclecompany_set.filter(is_active=True)

        if 'vehicle_company' in self.data:
            try:
                vehicle_company_id = int(self.data.get('vehicle_company'))
                self.fields['model'].queryset = Model.objects.filter(sub_category_id=vehicle_company_id, is_active=True)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['model'].queryset = self.instance.model.sub_category.model_set.filter(is_active=True)
            
        # Initialize fields from instance if it exists
        if self.instance.pk:
            # Set initial values for vehicle type and company
            self.initial['vehicle_type'] = self.instance.model.sub_category.category.pk
            self.initial['vehicle_company'] = self.instance.model.sub_category.pk
            
            # Set initial values for registration fields if instance has registration
            if hasattr(self.instance, 'registration'):
                self.initial['registration_number'] = self.instance.registration.registration_number
                self.initial['registration_date'] = self.instance.registration.registration_date
                self.initial['registration_end_date'] = self.instance.registration.registration_end_date
            
            # Set initial values for insurance fields if instance has insurance
            if hasattr(self.instance, 'insurance'):
                self.initial['policy_number'] = self.instance.insurance.policy_number
                self.initial['policy_provider'] = self.instance.insurance.policy_provider
                self.initial['coverage_type'] = self.instance.insurance.coverage_type
                self.initial['insurance_start_date'] = self.instance.insurance.start_date
                self.initial['insurance_end_date'] = self.instance.insurance.end_date
                self.initial['road_tax_details'] = self.instance.insurance.road_tax_details
                self.initial['fitness_expiry_date'] = self.instance.insurance.fitness_expiry_date
                self.initial['puc_expiry_date'] = self.instance.insurance.puc_expiry_date

    def save(self, commit=True):
        vehicle = super().save(commit=False)
        if self.vendor:
            vehicle.vendor = self.vendor

        # For new vehicles, create registration
        if not vehicle.pk:
            registration = Registration.objects.create(
                registration_number=self.cleaned_data['registration_number'],
                registration_date=self.cleaned_data['registration_date'],
                registration_end_date=self.cleaned_data['registration_end_date']
            )
            vehicle.registration = registration

        if commit:
            vehicle.save()
            self.save_m2m()  # Save many-to-many data for features

        return vehicle

class VehicleDocumentForm(forms.ModelForm):
    class Meta:
        model = VehicleDocument
        fields = ['rc_document', 'insurance_document', 'puc_document']

class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
        fields = ['category', 'company_name', 'is_active']

class VehicleBasicInfoForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['model', 'vendor', 'fuel_type', 'engine_number', 'chassis_number']

class VehicleDetailsForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['rental_rate', 'availability', 'image']

class VehicleFeaturesForm(forms.ModelForm):
    features = forms.ModelMultipleChoiceField(
        queryset=Features.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Vehicle
        fields = ['features']

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ['registration_number', 'registration_date', 'registration_end_date']

class InsuranceForm(forms.ModelForm):
    class Meta:
        model = Insurance
        fields = ['policy_number', 'policy_provider', 'coverage_type', 'start_date', 'end_date', 
                  'road_tax_details', 'fitness_expiry_date', 'puc_expiry_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'fitness_expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'puc_expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
