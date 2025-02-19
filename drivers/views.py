from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import DriverRegistrationForm, DriverLoginForm
from .models import Driver, DriverDocument, DriverApplicationLog, DriverAuth, DriverTrip, DriverBooking
from django.utils import timezone
from django.contrib.auth import login, logout
from functools import wraps
import logging
from django.http import JsonResponse
from django.urls import reverse
import stripe
from django.conf import settings
import traceback
from django.db import transaction

# Create a logger for the drivers app
logger = logging.getLogger(__name__)

# Create your views here.

def driver_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        driver_id = request.session.get('driver_id')
        if not driver_id:
            messages.error(request, 'Please login first')
            # Store the URL the user was trying to visit
            request.session['next'] = request.get_full_path()
            return redirect('drivers:driver_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def driver_login(request):
    if request.method == 'POST':
        form = DriverLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            
            try:
                driver_auth = DriverAuth.objects.get(email=email)
                if driver_auth.check_password(password):
                    driver = Driver.objects.get(auth=driver_auth)
                    
                    if driver.status == 'approved':
                        # Set session variables
                        request.session['driver_id'] = driver.id
                        request.session['driver_email'] = email
                        
                        # Update last login
                        driver_auth.last_login = timezone.now()
                        driver_auth.save()
                        
                        messages.success(request, 'Welcome back!')
                        return redirect('drivers:dashboard')
                    else:
                        status_messages = {
                            'pending_approval': 'Your application is still under review.',
                            'rejected': 'Your application has been rejected.',
                            'suspended': 'Your account has been suspended.'
                        }
                        messages.warning(request, status_messages.get(driver.status, 'Account not active'))
                        return redirect('drivers:approval_status')
                else:
                    messages.error(request, 'Invalid credentials')
            except (DriverAuth.DoesNotExist, Driver.DoesNotExist):
                messages.error(request, 'No driver account found with this email')
    else:
        form = DriverLoginForm()
    
    return render(request, 'drivers/driver_login.html', {'form': form})


@driver_login_required
def driver_dashboard(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        if driver.status != 'approved':
            messages.error(request, 'Your account is not approved yet')
            return redirect('drivers:approval_status')
            
        context = {
            'driver': driver,
            'status': driver.get_status_display(),
            'is_approved': driver.status == 'approved',
        }
        return render(request, 'drivers/dashboard.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

def driver_logout(request):
    # Clear driver session data
    request.session.pop('driver_id', None)
    request.session.pop('driver_email', None)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('drivers:driver_login')

def approval_status(request):
    driver_id = request.session.get('driver_id')
    if not driver_id:
        messages.error(request, 'Please login first')
        return redirect('drivers:driver_login')
        
    try:
        driver = Driver.objects.get(id=driver_id)
        context = {
            'driver': driver,
            'status': driver.get_status_display()
        }
        return render(request, 'drivers/approval_status.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

def register_driver(request):
    if request.method == 'POST':
        form = DriverRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():  # Add transaction management
                    # Create DriverAuth
                    driver_auth = DriverAuth.objects.create(
                        email=form.cleaned_data['email']
                    )
                    driver_auth.set_password(form.cleaned_data['password'])
                    driver_auth.save()
                    
                    # Create Driver profile
                    driver = Driver.objects.create(
                        auth=driver_auth,
                        full_name=form.cleaned_data['full_name'],
                        phone_number=form.cleaned_data['phone_number'],
                        license_number=form.cleaned_data['license_number'],
                        driving_experience=form.cleaned_data['driving_experience'],
                        driving_skill=form.cleaned_data['driving_skill'],
                        address=form.cleaned_data['address'],
                        city=form.cleaned_data['city'],
                        profile_photo=form.cleaned_data.get('profile_photo')
                    )
                    
                    # Create license document
                    if form.cleaned_data.get('license_document'):
                        DriverDocument.objects.create(
                            driver=driver,
                            document_type='license',
                            document=form.cleaned_data['license_document']
                        )
                    
                    messages.success(request, 'Registration successful! Please wait for admin approval.')
                    return redirect('drivers:approval_status')
                    
            except Exception as e:
                logger.error(f'Registration failed: {str(e)}')
                messages.error(request, 'Registration failed. Please try again.')
    else:
        form = DriverRegistrationForm()
    
    return render(request, 'drivers/driver_register.html', {'form': form})

@driver_login_required
def update_status(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        context = {
            'driver': driver,
            'status': driver.get_status_display()
        }
        
        if request.method == 'POST':
            new_status = request.POST.get('status')
            if new_status in ['available', 'unavailable']:
                driver.availability_status = new_status
                driver.save()
                messages.success(request, f'Status updated to {new_status}')
                return redirect('drivers:dashboard')
            else:
                messages.error(request, 'Invalid status')
        
        return render(request, 'drivers/update_status.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def driver_profile(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        if request.method == 'POST':
            # Handle profile update
            driver.full_name = request.POST.get('full_name', driver.full_name)
            driver.phone_number = request.POST.get('phone_number', driver.phone_number)
            driver.address = request.POST.get('address', driver.address)
            driver.city = request.POST.get('city', driver.city)
            
            if 'profile_photo' in request.FILES:
                driver.profile_photo = request.FILES['profile_photo']
            
            driver.save()
            messages.success(request, 'Profile updated successfully')
            return redirect('drivers:profile')
            
        context = {
            'driver': driver,
            'active_page': 'profile'
        }
        return render(request, 'drivers/profile.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def driver_trips(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        context = {
            'driver': driver,
            'trips': []  # Replace with actual trips data
        }
        return render(request, 'drivers/trips.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def driver_earnings(request):
    driver = Driver.objects.get(id=request.session['driver_id'])
    context = {
        'active_page': 'earnings',
        'driver': driver,
        'total_earnings': 0,  # Replace with actual calculation
        'monthly_earnings': 0,  # Replace with actual calculation
        'earnings': []  # Replace with actual earnings queryset
    }
    return render(request, 'drivers/earnings.html', context)

@driver_login_required
def driver_settings(request):
    driver = Driver.objects.get(id=request.session['driver_id'])
    context = {
        'active_page': 'settings',
        'driver': driver,
        'settings': {
            'email_notifications': True,
            'sms_notifications': True,
            'profile_visibility': False,
            'location_sharing': True,
            'language': 'en',
            'timezone': 'UTC'
        }  # Replace with actual settings from database
    }
    return render(request, 'drivers/settings.html', context)

@driver_login_required
def driver_support(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        context = {
            'driver': driver,
            'active_page': 'support'
        }
        return render(request, 'drivers/support.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def active_trips(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        current_time = timezone.now()
        
        # Get active bookings for the driver with more lenient time constraints
        active_bookings = DriverBooking.objects.filter(
            driver=driver,
            status='confirmed',
            payment_status='paid',
            end_date__gte=current_time  # Only check if booking hasn't ended
        ).select_related('user').order_by('start_date')

        context = {
            'active_bookings': active_bookings,
            'current_time': current_time,
            'driver': driver
        }
        return render(request, 'drivers/active_trips.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_login')

@driver_login_required
def start_trip(request, booking_id):
    booking = get_object_or_404(DriverBooking, id=booking_id)
    
    if not booking.can_start_trip():
        messages.error(request, 'Cannot start this trip at this time')
        return redirect('drivers:active_trips')
    
    try:
        with transaction.atomic():
            trip = DriverTrip.objects.create(
                driver=booking.driver,
                booking=booking,
                status='started',
                start_time=timezone.now(),
                start_location=request.POST.get('start_location', '')
            )
            booking.driver.availability_status = 'unavailable'
            booking.driver.save()
            
        messages.success(request, 'Trip started successfully')
    except Exception as e:
        messages.error(request, f'Error starting trip: {str(e)}')
    
    return redirect('drivers:active_trips')

@driver_login_required
def end_trip(request, booking_id):
    booking = get_object_or_404(DriverBooking, id=booking_id)
    
    if not booking.can_end_trip():
        messages.error(request, 'Cannot end this trip at this time')
        return redirect('drivers:active_trips')
    
    try:
        with transaction.atomic():
            trip = booking.trip
            trip.status = 'completed'
            trip.end_time = timezone.now()
            trip.end_location = request.POST.get('end_location', '')
            trip.save()
            
            booking.driver.availability_status = 'available'
            booking.driver.save()
            
        messages.success(request, 'Trip completed successfully')
    except Exception as e:
        messages.error(request, f'Error ending trip: {str(e)}')
    
    return redirect('drivers:active_trips')

@driver_login_required
def completed_trips(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        completed_trips = DriverTrip.objects.filter(
            driver=driver,
            status='completed'
        ).order_by('-end_time')
        context = {
            'driver': driver,
            'trips': completed_trips,
            'active_page': 'completed_trips'
        }
        return render(request, 'drivers/trips.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def earnings_history(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        completed_trips = DriverTrip.objects.filter(
            driver=driver,
            status='completed'
        ).order_by('-end_time')
        context = {
            'driver': driver,
            'trips': completed_trips,
            'active_page': 'earnings_history'
        }
        return render(request, 'drivers/earnings_history.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def documents(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        if request.method == 'POST' and request.FILES:
            # Handle document upload
            document_type = request.POST.get('document_type')
            document_file = request.FILES.get('document')
            
            if document_type and document_file:
                # Create or update document
                DriverDocument.objects.update_or_create(
                    driver=driver,
                    document_type=document_type,
                    defaults={'document': document_file, 'is_verified': False}
                )
                messages.success(request, 'Document uploaded successfully')
                return redirect('drivers:documents')
            
        documents = DriverDocument.objects.filter(driver=driver)
        context = {
            'driver': driver,
            'documents': documents,
            'active_page': 'documents'
        }
        return render(request, 'drivers/documents.html', context)
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def change_password(request):
    try:
        driver = Driver.objects.select_related('auth').get(id=request.session['driver_id'])
        
        if request.method == 'POST':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Validate current password
            if not driver.auth.check_password(current_password):
                messages.error(request, 'Current password is incorrect')
                return redirect('drivers:profile')
            
            # Validate new password
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match')
                return redirect('drivers:profile')
            
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long')
                return redirect('drivers:profile')
            
            # Update password
            driver.auth.set_password(new_password)
            driver.auth.save()
            
            messages.success(request, 'Password changed successfully')
            return redirect('drivers:profile')
            
        return redirect('drivers:profile')
    except Driver.DoesNotExist:
        messages.error(request, 'Driver profile not found')
        return redirect('drivers:driver_register')

@driver_login_required
def update_settings(request):
    if request.method == 'POST':
        try:
            driver = Driver.objects.get(id=request.session['driver_id'])
            # Update notification settings
            email_notifications = request.POST.get('email_notifications') == 'on'
            sms_notifications = request.POST.get('sms_notifications') == 'on'
            
            # Save to settings model or update driver preferences
            # For now, just show a success message
            messages.success(request, 'Notification settings updated successfully')
            
        except Driver.DoesNotExist:
            messages.error(request, 'Driver profile not found')
    
    return redirect('drivers:settings')

@driver_login_required
def update_privacy(request):
    if request.method == 'POST':
        try:
            driver = Driver.objects.get(id=request.session['driver_id'])
            # Update privacy settings
            profile_visibility = request.POST.get('profile_visibility') == 'on'
            location_sharing = request.POST.get('location_sharing') == 'on'
            
            # Save to settings model or update driver preferences
            # For now, just show a success message
            messages.success(request, 'Privacy settings updated successfully')
            
        except Driver.DoesNotExist:
            messages.error(request, 'Driver profile not found')
    
    return redirect('drivers:settings')

@driver_login_required
def update_account(request):
    if request.method == 'POST':
        try:
            driver = Driver.objects.get(id=request.session['driver_id'])
            # Update account settings
            language = request.POST.get('language')
            timezone = request.POST.get('timezone')
            
            # Save to settings model or update driver preferences
            # For now, just show a success message
            messages.success(request, 'Account settings updated successfully')
            
        except Driver.DoesNotExist:
            messages.error(request, 'Driver profile not found')
    
    return redirect('drivers:settings')

@login_required
def book_driver(request, driver_id):
    driver = get_object_or_404(Driver, id=driver_id, status='approved', availability_status='available')
    
    if request.method == 'POST':
        try:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            if not start_date or not end_date:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please provide both start and end dates'
                })

            # Convert string dates to datetime objects
            start_datetime = timezone.datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            end_datetime = timezone.datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            
            # Make them timezone aware
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)

            # Check for overlapping bookings
            overlapping_bookings = DriverBooking.objects.filter(
                driver=driver,
                status='confirmed',
                payment_status='paid',
                start_date__lt=end_datetime,
                end_date__gt=start_datetime
            ).exists()

            if overlapping_bookings:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Selected dates are not available',
                    'show_modal': True
                })
            
            # Calculate duration in days
            duration = (end_datetime - start_datetime).days + 1
            total_amount = duration * 500.00  # Base rate of 500 per day
            
            # Create driver booking
            driver_booking = DriverBooking.objects.create(
                driver=driver,
                user=request.user,
                start_date=start_datetime,
                end_date=end_datetime,
                amount=total_amount,
                status='pending',
                payment_status='pending'
            )
            
            # Create Stripe payment session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'inr',
                        'unit_amount': int(driver_booking.amount * 100),
                        'product_data': {
                            'name': f'Driver Booking - {driver.full_name}',
                            'description': f'From {start_date} to {end_date}'
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(
                    reverse('drivers:driver_booking_success')
                ) + f'?booking_id={driver_booking.id}',
                cancel_url=request.build_absolute_uri(
                    reverse('drivers:driver_booking_cancel')
                ) + f'?booking_id={driver_booking.id}',
            )
            
            return JsonResponse({
                'status': 'success',
                'session_id': session.id
            })
            
        except Exception as e:
            logger.error(f"Error in driver booking: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    context = {
        'driver': driver,
        'stripe_publishable_key': settings.STRIPE_PUBLIC_KEY
    }
    return render(request, 'drivers/book_driver.html', context)

@login_required
def check_driver_availability(request, driver_id):
    if request.method == 'POST':
        try:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            if not start_date or not end_date:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please provide both start and end dates'
                })

            start_datetime = timezone.make_aware(
                timezone.datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            )
            end_datetime = timezone.make_aware(
                timezone.datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            )

            # Check for overlapping bookings
            overlapping_bookings = DriverBooking.objects.filter(
                driver_id=driver_id,
                status__in=['confirmed', 'pending'],
                payment_status='paid',
                start_date__lt=end_datetime,
                end_date__gt=start_datetime
            )

            if overlapping_bookings.exists():
                # Get the next available date after the last overlapping booking
                next_available = overlapping_bookings.order_by('-end_date').first().end_date
                return JsonResponse({
                    'status': 'error',
                    'available': False,
                    'message': f'Selected dates are not available. Next available date is {next_available.strftime("%Y-%m-%d %H:%M")}',
                    'next_available': next_available.isoformat()
                })

            return JsonResponse({
                'status': 'success',
                'available': True,
                'message': 'Driver is available for selected dates'
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })

@login_required
def driver_booking_success(request):
    booking_id = request.GET.get('booking_id')
    if not booking_id:
        messages.error(request, 'No booking ID provided')
        return redirect('home')
    
    try:
        driver_booking = DriverBooking.objects.get(id=booking_id)
        
        # Update booking status
        driver_booking.status = 'confirmed'
        driver_booking.payment_status = 'paid'
        driver_booking.save()
        
        messages.success(request, 'Driver booking confirmed successfully!')
        
        # If there's an associated booking, redirect to its detail page
        if hasattr(driver_booking, 'booking') and driver_booking.booking:
            return redirect('booking_detail', booking_id=driver_booking.booking.booking_id)
        else:
            # If no associated booking, redirect to driver booking list
            return redirect('drivers:driver_booking_list')
            
    except DriverBooking.DoesNotExist:
        messages.error(request, 'Invalid booking ID')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'Error processing booking: {str(e)}')
        return redirect('home')

@login_required
def driver_booking_cancel(request):
    booking_id = request.GET.get('booking_id')
    driver_booking = get_object_or_404(DriverBooking, id=booking_id)
    
    # Update driver availability
    driver_booking.driver.availability_status = 'available'
    driver_booking.driver.save()
    
    # Update booking status
    driver_booking.status = 'cancelled'
    driver_booking.save()
    
    messages.warning(request, 'Driver booking was cancelled.')
    return redirect('mainapp:booking_detail', booking_id=driver_booking.booking.booking_id)

@login_required
def driver_booking_list(request):
    try:
        # Get all bookings for the current user
        bookings = DriverBooking.objects.filter(user=request.user).order_by('-created_at')
        
        context = {
            'bookings': bookings,
            'active_page': 'bookings',
            'has_bookings': bookings.exists()  # Add this to check if there are any bookings
        }
        return render(request, 'booking_list.html', context)
    except Exception as e:
        messages.error(request, 'Error retrieving your bookings')
        return redirect('home')
