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
        fields = ['business_name', 'address', 'city', 'state', 'zip_code', 'contact_number']

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
    availability = forms.BooleanField(required=False)
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

    class Meta:
        model = Vehicle
        fields = ['vehicle_type', 'vehicle_company', 'model', 'fuel_type', 'engine_number', 'chassis_number', 
                  'rental_rate', 'availability', 'image', 'features']

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

    def save(self, commit=True):
        vehicle = super().save(commit=False)
        if self.vendor:
            vehicle.vendor = self.vendor

        # Create Registration
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