from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.hashers import make_password
from .models import User, UserProfile, Vendor

class UserRegistrationForm(forms.ModelForm):
    fullname = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.email = self.cleaned_data['email']
        fullname = self.cleaned_data['fullname']
        first_name, last_name = fullname.split(' ', 1)
        user.first_name = first_name
        user.last_name = last_name
        user.role = 'user'
        if commit:
            user.save()
        return user
    
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'address', 'city', 'pin_code', 'license_number', 'is_complete']

class VendorUserForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = 'vendor'
        if commit:
            user.save()
        return user

class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['business_name', 'address', 'city', 'state', 'zip_code', 'contact_number']

class VendorLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)