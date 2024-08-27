from django import forms
from vendor.models import VehicleType, VehicleCompany, Model, Features

class VehicleTypeForm(forms.ModelForm):
    class Meta:
        model = VehicleType
        fields = ['category_name']

class VehicleCompanyForm(forms.ModelForm):
    class Meta:
        model = VehicleCompany
        fields = ['category', 'company_name']

class ModelForm(forms.ModelForm):
    class Meta:
        model = Model
        fields = ['sub_category', 'model_name', 'model_year']

class FeaturesForm(forms.ModelForm):
    class Meta:
        model = Features
        fields = ['feature_name']