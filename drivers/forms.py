from django import forms
from django.contrib.auth.hashers import make_password
from .models import Driver, DriverAuth, DriverDocument
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate

class DriverRegistrationForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    full_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    license_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    driving_experience = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    driving_skill = forms.ChoiceField(
        choices=Driver.DRIVING_SKILLS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    city = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    profile_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    license_document = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if DriverAuth.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered. Please use a different email or login to your existing account.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match")
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        # Create DriverAuth instance
        driver_auth = DriverAuth.objects.create(
            email=data['email'],
            password=make_password(data['password']),
            is_active=True
        )

        # Create Driver instance
        driver = Driver.objects.create(
            auth=driver_auth,
            full_name=data['full_name'],
            phone_number=data['phone_number'],
            address=data['address'],
            city=data['city'],
            license_number=data['license_number'],
            driving_experience=data['driving_experience'],
            driving_skill=data['driving_skill'],
            profile_photo=data.get('profile_photo')
        )

        # Create DriverDocument if license document is provided
        if data.get('license_document'):
            DriverDocument.objects.create(
                driver=driver,
                license_document=data['license_document']
            )

        return driver

class DriverLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class DriverUpdateForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ['full_name', 'phone_number', 'address', 'city', 'profile_photo']

class DriverDocumentForm(forms.ModelForm):
    class Meta:
        model = DriverDocument
        fields = ['document_type', 'document']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document': forms.FileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document_type'].widget.attrs.update({
            'class': 'form-select',
            'required': True
        })
        self.fields['document'].widget.attrs.update({
            'class': 'form-control',
            'required': True
        })

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if document:
            # Add file size validation (5MB limit)
            if document.size > 5 * 1024 * 1024:
                raise ValidationError("File size must be under 5MB")
            # Add file type validation
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
            if document.content_type not in allowed_types:
                raise ValidationError("Only PDF, JPEG, and PNG files are allowed")
        return document
