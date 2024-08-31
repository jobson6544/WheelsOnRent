from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, UserProfileForm, UserEditForm, UserProfileEditForm
from .models import UserProfile, Booking  # Import UserProfile here
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import logout  # Ensure this import is present
from vendor.models import Vehicle
from django.utils import timezone  # Add this import

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
    # Try to get the existing profile, or create a new one if it doesn't exist
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.is_complete = True  # Mark the profile as complete
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('home')  # or wherever you want to redirect after successful submission
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'complete_profile.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if hasattr(user, 'is_first_login') and user.is_first_login:
                user.is_first_login = False
                user.save()
                return redirect('complete_profile')
            return redirect('home')
        else:
            messages.error(request, "Invalid email or password.")
    return render(request, 'user_login.html')

def redirect_after_login(user):
    try:
        profile = user.profile
        if not profile.is_complete:
            return redirect('complete_profile')
    except UserProfile.DoesNotExist:
        return redirect('complete_profile')
    return redirect('home')

def home(request):
    vehicles = Vehicle.objects.filter(status=1).select_related('vendor', 'model__sub_category__category').prefetch_related('features')
    return render(request, 'home.html', {'vehicles': vehicles})

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

@login_required
def book_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle.objects.select_related('model__sub_category__category', 'vendor').prefetch_related('features'), vehicle_id=vehicle_id, status=1)
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Create a new booking
        booking = Booking.objects.create(
            user=request.user,
            vehicle=vehicle,
            start_date=start_date,
            end_date=end_date,
            status='pending'
        )
        
        messages.success(request, 'Booking request submitted successfully!')
        return redirect('user_booking_history')  # Redirect to the new booking history page
    
    return render(request, 'book_vehicle.html', {'vehicle': vehicle})

@login_required
def user_booking_history(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-start_date')
    return render(request, 'user_booking_history.html', {'bookings': bookings})

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    
    if request.method == 'POST':
        if booking.status in ['pending', 'confirmed']:
            # Check if the booking start date is more than 24 hours away
            if booking.start_date > timezone.now() + timezone.timedelta(hours=24):
                booking.status = 'cancelled'
                booking.save()
                messages.success(request, 'Your booking has been successfully cancelled.')
            else:
                messages.error(request, 'Bookings can only be cancelled more than 24 hours before the start time.')
        else:
            messages.error(request, 'This booking cannot be cancelled.')
    
    return redirect('user_booking_history')

@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, 'profile_view.html', {'profile': profile})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)
        profile_form = UserProfileEditForm(request.POST, request.FILES, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('profile_view')
    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = UserProfileEditForm(instance=request.user.profile)
    
    return render(request, 'edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })