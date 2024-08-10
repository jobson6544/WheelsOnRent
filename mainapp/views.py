from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, UserProfileForm
from .models import UserProfile  # Import UserProfile here
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import logout  # Ensure this import is present

User = get_user_model()

def index(request):
    return render(request, 'index.html')

def customer_register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'user'  # Set the role for the user if needed
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')  # Specify the backend
            return redirect('complete_profile')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

@login_required(login_url='login')
def complete_profile(request):
    # Attempt to get the user's profile or create a new one if it doesn't exist
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile(user=request.user)
        profile.save()  # Save the new profile instance

    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if profile_form.is_valid():
            profile = profile_form.save(commit=False)
            profile.is_complete = True  # Mark the profile as complete
            profile.save()  # Save the profile
            return redirect('home')  # Redirect to the home page after saving
    else:
        profile_form = UserProfileForm(instance=profile)  # Pre-fill the form with existing profile data
    
    context = {
        'profile_form': profile_form,
    }
    return render(request, 'complete_profile.html', context)

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if user.is_first_login:
                    user.is_first_login = False
                    user.save()
                    return redirect('complete_profile')
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'user_login.html', {'form': form})

def redirect_after_login(user):
    try:
        profile = user.profile
        if not profile.is_complete:
            return redirect('complete_profile')
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    return redirect('home')

def home(request):
    return render(request, 'home.html')

def success(request):
    return render(request, 'success.html')

def logout_view(request):
    logout(request)
    return redirect('index')  # Redirect to home page after logout

@login_required(login_url='login')
def profile(request):
    user = request.user
    try:
        userprofile = user.profile
    except UserProfile.DoesNotExist:
        userprofile = UserProfile.objects.create(user=user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=userprofile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = user
            profile.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=userprofile)

    context = {
        'user': user,
        'form': form,
        'userprofile': userprofile,
    }
    return render(request, 'profile.html', context)

def vendor_login(request):
    if request.method == 'POST':
        form = VendorLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(request, email=email, password=password)
            
            if user is not None and user.role == 'vendor':
                try:
                    vendor = Vendor.objects.get(user=user)
                    if vendor.status == 'approved':
                        login(request, user)
                        return redirect('vendor_dashboard')
                    elif vendor.status == 'pending':
                        messages.info(request, "Your application is under review.")
                        return redirect('vendor_pending')
                    else:
                        messages.error(request, "Your application has been rejected.")
                        return redirect('vendor_rejected')
                except Vendor.DoesNotExist:
                    messages.error(request, "Vendor profile not found.")
            else:
                messages.error(request, "Invalid login credentials or not authorized as a vendor.")
        else:
            messages.error(request, "Invalid form submission.")
    else:
        form = VendorLoginForm()
    
    return render(request, 'vendor_login.html', {'form': form})