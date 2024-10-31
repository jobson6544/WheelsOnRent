from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from .models import User, UserProfile, Feedback

class UserRegistrationForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9]+$',
                message='Username can only contain letters and numbers.',
            ),
        ]
    )
    full_name = forms.CharField(
        max_length=100, 
        required=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s]+$',
                message='Full name can only contain letters and spaces.',
            ),
        ]
    )
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'full_name', 'email', 'password']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.email = self.cleaned_data['email']
        fullname = self.cleaned_data['full_name']
        first_name, last_name = fullname.split(' ', 1)
        user.first_name = first_name
        user.last_name = last_name
        user.role = 'user'
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r'^\d{10}$',
                message="Phone number must be 10 digits.",
            ),
        ]
    )
    address = forms.CharField(max_length=255)
    city = forms.CharField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s]+$',
                message='City name can only contain letters and spaces.',
            ),
        ]
    )
    pin_code = forms.CharField(
        max_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message='Pin code must be 6 digits.',
            ),
        ]
    )
    license_number = forms.CharField(
        max_length=16,
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{2}\d{2}\s?\d{4}\s?\d{7}$',
                message='Invalid license number format. It should be in the format: "DL01 2022 0123456"',
            ),
        ]
    )
    profile_photo = forms.ImageField(required=False)
    license_front = forms.ImageField(required=True)
    license_back = forms.ImageField(required=True)

    class Meta:
        model = UserProfile
        fields = ['phone_number', 'license_number', 'address', 'city', 'pin_code', 'profile_photo', 'license_front', 'license_back']

class UserEditForm(forms.ModelForm):
    full_name = forms.CharField(max_length=255, required=True)

    class Meta:
        model = User
        fields = ['full_name', 'username']

class UserProfileEditForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            ),
        ]
    )
    license_number = forms.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{2}\d{2}\s?\d{4}\s?\d{7}$',
                message='Invalid license number format. It should be in the format: "DL01 2022 0123456"',
            ),
        ]
    )
    address = forms.CharField(max_length=255)
    city = forms.CharField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s]+$',
                message='City name can only contain letters and spaces.',
            ),
        ]
    )
    pin_code = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message='Pin code must be 6 digits.',
            ),
        ]
    )
    profile_photo = forms.ImageField(required=False)
    license_front = forms.ImageField(required=False)
    license_back = forms.ImageField(required=False)

    class Meta:
        model = UserProfile
        fields = ['phone_number', 'license_number', 'address', 'city', 'pin_code', 'profile_photo', 'license_front', 'license_back']

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'star-rating'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your experience with this vehicle rental...'
            })
        }