from django import forms
from django.contrib.auth.forms import UserCreationForm
from mainapp.models import User
from vendor.models import Vendor, VehicleType, VehicleCompany, Model, Registration, Features, Vehicle

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
    class Meta:
        model = Vehicle
        fields = ['model', 'rental_rate', 'features', 'availability', 'image']
        widgets = {
            'availability': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'features': forms.CheckboxSelectMultiple(),
        }

    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects.all(), required=True)
    vehicle_company = forms.ModelChoiceField(queryset=VehicleCompany.objects.none(), required=True)
    
    registration_number = forms.CharField(max_length=255, required=True)
    registration_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    registration_end_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    
    image = forms.ImageField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['features'].queryset = Features.objects.all()
        self.fields['model'].queryset = Model.objects.none()

        if 'vehicle_type' in self.data:
            try:
                vehicle_type_id = int(self.data.get('vehicle_type'))
                self.fields['vehicle_company'].queryset = VehicleCompany.objects.filter(category_id=vehicle_type_id)
            except (ValueError, TypeError):
                pass
        
        if 'vehicle_company' in self.data:
            try:
                company_id = int(self.data.get('vehicle_company'))
                self.fields['model'].queryset = Model.objects.filter(sub_category_id=company_id)
            except (ValueError, TypeError):
                pass

    def clean(self):
        cleaned_data = super().clean()
        model = cleaned_data.get('model')
        vehicle_company = cleaned_data.get('vehicle_company')

        if model and vehicle_company:
            if model.sub_category != vehicle_company:
                raise forms.ValidationError("Selected model does not belong to the selected company.")

        return cleaned_data

class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
        fields = ['category', 'company_name', 'is_active']