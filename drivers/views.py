from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import DriverRegistrationForm, DriverLoginForm
from .models import Driver, DriverDocument, DriverApplicationLog, DriverAuth, DriverTrip, DriverBooking, Vehicle
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
from django.db import models
import decimal
import random
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime

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
        
        # Get total completed trips
        total_trips = DriverTrip.objects.filter(
            driver=driver,
            status='completed'
        ).count()
        
        # Get recent driver bookings
        recent_bookings = DriverBooking.objects.filter(
            driver=driver
        ).order_by('-created_at')[:5]  # Get last 5 bookings
            
        context = {
            'driver': driver,
            'status': driver.get_status_display(),
            'is_approved': driver.status == 'approved',
            'total_trips': total_trips,
            'driver_bookings': recent_bookings,
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

@login_required
def active_trips(request):
    try:
        driver = get_object_or_404(Driver, user=request.user)
        
        # Get all confirmed and in_progress bookings for the driver
        bookings = DriverBooking.objects.filter(
            driver=driver,
            status__in=['confirmed', 'in_progress']
        ).order_by('service_date', 'start_date', 'booking_date')
        
        bookings_data = []
        current_time = timezone.now()
        
        for booking in bookings:
            can_start = False
            start_time = None
            has_pickup = bool(booking.pickup_location)
            
            # Check if the trip can be started based on booking type
            if booking.booking_type == 'specific_date':
                booking_datetime = datetime.combine(
                    booking.booking_date,
                    booking.start_time
                ).replace(tzinfo=timezone.get_current_timezone())
                can_start = current_time >= booking_datetime
                if not can_start:
                    start_time = booking_datetime.strftime('%I:%M %p, %b %d')
                    
            elif booking.booking_type == 'point_to_point':
                service_datetime = booking.service_date
                if service_datetime:
                    can_start = current_time.date() >= service_datetime.date()
                    if not can_start:
                        start_time = service_datetime.strftime('%b %d, %Y')
                        
            else:  # with_vehicle
                start_datetime = booking.start_date
                if start_datetime:
                    can_start = current_time >= start_datetime
                    if not can_start:
                        start_time = start_datetime.strftime('%I:%M %p, %b %d')
            
            # Only allow starting if booking is confirmed
            can_start = can_start and booking.status == 'confirmed'
            
            bookings_data.append({
                'booking': booking,
                'can_start': can_start,
                'start_time': start_time,
                'has_pickup': has_pickup
            })
        
        context = {
            'bookings_data': bookings_data,
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
        }
        
        return render(request, 'drivers/active_trips.html', context)
        
    except Exception as e:
        logger.error(f"Error in active_trips view: {str(e)}")
        messages.error(request, 'An error occurred while loading active trips.')
        return redirect('drivers:dashboard')

@login_required
def start_trip(request, booking_id):
    try:
        # Get the booking and verify it belongs to the logged-in driver
        booking = get_object_or_404(DriverBooking, id=booking_id)
        driver = get_object_or_404(Driver, user=request.user)
        
        if booking.driver.id != driver.id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized access'}, status=403)
        
        # Check if the trip can be started
        if booking.status != 'confirmed':
            return JsonResponse({'status': 'error', 'message': 'Booking is not in confirmed status'})
            
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Store OTP in session with timestamp
        request.session[f'trip_otp_{booking_id}'] = {
            'otp': otp,
            'timestamp': timezone.now().timestamp(),
            'attempts': 0
        }
        
        # Prepare email content
        context = {
            'user_name': booking.user.get_full_name(),
            'otp': otp,
            'booking': booking,
            'driver_name': driver.user.get_full_name()
        }
        
        html_message = render_to_string('drivers/email/trip_start_otp.html', context)
        plain_message = strip_tags(html_message)
        
        # Send OTP email
        try:
            send_mail(
                'Trip Start Verification OTP',
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [booking.user.email],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send OTP email. Please try again.'
            })
        
        return JsonResponse({'status': 'success', 'message': 'OTP sent successfully'})
        
    except Exception as e:
        logger.error(f"Error in start_trip: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while starting the trip'
        })

@login_required
def verify_trip_otp(request, booking_id):
    try:
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
            
        otp = request.POST.get('otp')
        if not otp:
            return JsonResponse({'status': 'error', 'message': 'OTP is required'})
            
        # Get stored OTP data
        stored_otp_data = request.session.get(f'trip_otp_{booking_id}')
        if not stored_otp_data:
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please request a new one.'})
            
        # Check OTP expiration (10 minutes)
        current_time = timezone.now().timestamp()
        if current_time - stored_otp_data['timestamp'] > 600:  # 10 minutes
            del request.session[f'trip_otp_{booking_id}']
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please request a new one.'})
            
        # Check attempts
        if stored_otp_data['attempts'] >= 3:
            del request.session[f'trip_otp_{booking_id}']
            return JsonResponse({'status': 'error', 'message': 'Too many attempts. Please request a new OTP.'})
            
        # Increment attempts
        stored_otp_data['attempts'] += 1
        request.session[f'trip_otp_{booking_id}'] = stored_otp_data
        
        # Verify OTP
        if otp != stored_otp_data['otp']:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid OTP. {3 - stored_otp_data["attempts"]} attempts remaining.'
            })
            
        # Get booking and start trip
        booking = get_object_or_404(DriverBooking, id=booking_id)
        driver = get_object_or_404(Driver, user=request.user)
        
        if booking.driver.id != driver.id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized access'}, status=403)
            
        # Create or update trip
        trip, created = DriverTrip.objects.get_or_create(
            booking=booking,
            defaults={
                'start_time': timezone.now(),
                'status': 'started'
            }
        )
        
        if not created:
            trip.start_time = timezone.now()
            trip.status = 'started'
            trip.save()
            
        # Update booking status
        booking.status = 'in_progress'
        booking.save()
        
        # Clear OTP from session
        del request.session[f'trip_otp_{booking_id}']
        
        return JsonResponse({
            'status': 'success',
            'message': 'Trip started successfully',
            'redirect_url': reverse('drivers:active_trips')
        })
        
    except Exception as e:
        logger.error(f"Error in verify_trip_otp: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while verifying OTP'
        })

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
            # Log the POST data for debugging
            logger.debug(f"POST data received: {request.POST}")
            
            booking_type = request.POST.get('booking_type')
            if not booking_type:
                logger.error("No booking type provided")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please select a booking type'
                })

            # Initialize booking data
            booking_data = {
                'driver': driver,
                'user': request.user,
                'booking_type': booking_type,
                'status': 'pending',
                'payment_status': 'pending'
            }

            # Handle different booking types
            if booking_type == 'specific_date':
                booking_date = request.POST.get('booking_date')
                start_time = request.POST.get('start_time')
                end_time = request.POST.get('end_time')
                
                logger.debug(f"Specific date booking data: date={booking_date}, start={start_time}, end={end_time}")
                
                if not all([booking_date, start_time, end_time]):
                    logger.error("Missing required specific date fields")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide booking date, start time and end time'
                    })

                try:
                    # Convert strings to date and time objects
                    booking_date = timezone.datetime.strptime(booking_date, '%Y-%m-%d').date()
                    start_time = timezone.datetime.strptime(start_time, '%H:%M').time()
                    end_time = timezone.datetime.strptime(end_time, '%H:%M').time()
                except ValueError as e:
                    logger.error(f"Date/time parsing error: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid date or time format'
                    })
                
                # Validate times
                if start_time >= end_time:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'End time must be after start time'
                    })
                
                booking_data.update({
                    'booking_date': booking_date,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
                # Calculate hours and amount
                hours = ((end_time.hour * 60 + end_time.minute) - 
                        (start_time.hour * 60 + start_time.minute)) / 60
                total_amount = hours * 100.00  # Rate of 100 per hour

            elif booking_type == 'point_to_point':
                # Get form data
                pickup_location = request.POST.get('pickup_location', '').strip()
                drop_location = request.POST.get('drop_location', '').strip()
                service_date = request.POST.get('service_date', '').strip()
                
                # Get coordinates
                try:
                    pickup_latitude = float(request.POST.get('pickup_lat', 0))
                    pickup_longitude = float(request.POST.get('pickup_lng', 0))
                    drop_latitude = float(request.POST.get('drop_lat', 0))
                    drop_longitude = float(request.POST.get('drop_lng', 0))
                    
                    logger.debug(f"Received coordinates: pickup({pickup_latitude}, {pickup_longitude}), drop({drop_latitude}, {drop_longitude})")
                    
                    if not all([pickup_latitude, pickup_longitude, drop_latitude, drop_longitude]):
                        logger.error("Missing or zero coordinates")
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Please select locations from the Google Maps suggestions'
                        })
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid coordinate values: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid location coordinates'
                    })
                
                logger.debug(f"Point to point data: pickup={pickup_location}, drop={drop_location}, date={service_date}")
                
                # Validate required fields
                if not all([pickup_location, drop_location, service_date]):
                    logger.error("Missing required point-to-point fields")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide pickup location, drop location, and service date'
                    })

                try:
                    service_date = timezone.datetime.strptime(service_date, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f"Invalid service date format: {service_date}")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid service date format'
                    })
                
                booking_data.update({
                    'pickup_location': pickup_location,
                    'drop_location': drop_location,
                    'service_date': service_date,
                    'pickup_latitude': pickup_latitude,
                    'pickup_longitude': pickup_longitude,
                    'drop_latitude': drop_latitude,
                    'drop_longitude': drop_longitude
                })
                
                # Calculate total amount based on distance
                try:
                    distance = request.POST.get('distance', '').strip()
                    if distance:
                        distance_km = float(distance.replace(' km', ''))
                        base_price = 1000.00
                        price_per_km = 15.00
                        total_amount = base_price + (distance_km * price_per_km)
                    else:
                        total_amount = 1000.00  # Default fixed rate
                except (ValueError, TypeError):
                    logger.error(f"Invalid distance format: {distance}")
                    total_amount = 1000.00  # Default to fixed rate if distance parsing fails

            elif booking_type == 'with_vehicle':
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                vehicle_id = request.POST.get('vehicle_id')
                
                logger.debug(f"With vehicle booking data: start={start_date}, end={end_date}, vehicle={vehicle_id}")
                
                if not all([start_date, end_date, vehicle_id]):
                    logger.error("Missing required vehicle booking fields")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide start date, end date, and select a vehicle'
                    })

                try:
                    # Get the vehicle first
                    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='available')
                    
                    # Parse dates in YYYY-MM-DD HH:mm format
                    try:
                        start_datetime = timezone.make_aware(timezone.datetime.strptime(start_date, '%Y-%m-%d %H:%M'))
                        end_datetime = timezone.make_aware(timezone.datetime.strptime(end_date, '%Y-%m-%d %H:%M'))
                    except ValueError as e:
                        logger.error(f"Date parsing error: {str(e)}")
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Invalid date format. Please use YYYY-MM-DD HH:mm format'
                        })
                    
                    if start_datetime >= end_datetime:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'End date must be after start date'
                        })

                    # Check vehicle availability
                    vehicle_is_available = not DriverBooking.objects.filter(
                        vehicle=vehicle,
                        status__in=['confirmed', 'pending'],
                        payment_status='paid',
                        start_date__lt=end_datetime,
                        end_date__gt=start_datetime
                    ).exists()

                    if not vehicle_is_available:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Selected vehicle is not available for these dates'
                        })

                    # Calculate duration and total amount
                    duration = (end_datetime - start_datetime).days + 1
                    driver_rate = decimal.Decimal('500.00')  # Convert to Decimal
                    total_amount = duration * (driver_rate + vehicle.rental_rate)  # Both values are now Decimal

                    # Update booking data
                    booking_data.update({
                        'start_date': start_datetime,
                        'end_date': end_datetime,
                        'vehicle': vehicle,
                        'amount': total_amount
                    })

                except Vehicle.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid vehicle selected'
                    })
                except Exception as e:
                    logger.error(f"Error processing vehicle booking: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': str(e)
                    })

            # Check for overlapping bookings
            overlapping_bookings = DriverBooking.objects.filter(
                driver=driver,
                status='confirmed',
                payment_status='paid'
            )

            if booking_type == 'specific_date':
                overlapping_bookings = overlapping_bookings.filter(
                    booking_type='specific_date',
                    booking_date=booking_data['booking_date']
                ).filter(
                    models.Q(
                        start_time__lt=booking_data['end_time'],
                        end_time__gt=booking_data['start_time']
                    )
                )
            elif booking_type == 'with_vehicle':
                overlapping_bookings = overlapping_bookings.filter(
                    start_date__lt=booking_data['end_date'],
                    end_date__gt=booking_data['start_date']
                )
            else:  # point_to_point
                overlapping_bookings = overlapping_bookings.filter(
                    service_date=booking_data['service_date']
                )

            if overlapping_bookings.exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Selected time slot is not available',
                    'show_modal': True
                })

            # Create driver booking
            booking_data['amount'] = total_amount
            driver_booking = DriverBooking.objects.create(**booking_data)
            
            # Create Stripe payment session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'inr',
                        'unit_amount': int(total_amount * 100),
                        'product_data': {
                            'name': f'Driver Booking - {driver.full_name}',
                            'description': get_booking_description(booking_type, booking_data)
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
    
    # Get available vehicles for 'with_vehicle' booking type
    available_vehicles = Vehicle.objects.filter(status='available', availability=True)
    
    context = {
        'driver': driver,
        'stripe_publishable_key': settings.STRIPE_PUBLIC_KEY,
        'available_vehicles': available_vehicles,
        'booking_types': DriverBooking.BOOKING_TYPE_CHOICES,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
    }
    return render(request, 'drivers/book_driver.html', context)

def get_booking_description(booking_type, booking_data):
    if booking_type == 'specific_date':
        return f"Single Day Booking on {booking_data['booking_date']} from {booking_data['start_time']} to {booking_data['end_time']}"
    elif booking_type == 'point_to_point':
        return f"Point to Point Service from {booking_data['pickup_location']} to {booking_data['drop_location']} on {booking_data['service_date']}"
    else:
        return f"Vehicle Booking from {booking_data['start_date']} to {booking_data['end_date']}"

@login_required
def check_driver_availability(request, driver_id):
    if request.method == 'POST':
        try:
            booking_type = request.POST.get('booking_type')
            driver = get_object_or_404(Driver, id=driver_id)

            if booking_type == 'specific_date':
                booking_date = request.POST.get('booking_date')
                start_time = request.POST.get('start_time')
                end_time = request.POST.get('end_time')
                
                if not all([booking_date, start_time, end_time]):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide booking date, start time and end time'
                    })

                booking_date = timezone.datetime.strptime(booking_date, '%Y-%m-%d').date()
                start_time = timezone.datetime.strptime(start_time, '%H:%M').time()
                end_time = timezone.datetime.strptime(end_time, '%H:%M').time()

                overlapping_bookings = DriverBooking.objects.filter(
                    driver=driver,
                    status__in=['confirmed', 'pending'],
                    payment_status='paid',
                    booking_type='specific_date',
                    booking_date=booking_date
                ).filter(
                    models.Q(
                        start_time__lt=end_time,
                        end_time__gt=start_time
                    )
                )

            elif booking_type == 'with_vehicle':
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                
                if not all([start_date, end_date]):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide start and end dates'
                    })

                try:
                    # Parse dates in YYYY-MM-DD HH:mm format
                    start_datetime = timezone.make_aware(
                        timezone.datetime.strptime(start_date, '%Y-%m-%d %H:%M')
                    )
                    end_datetime = timezone.make_aware(
                        timezone.datetime.strptime(end_date, '%Y-%m-%d %H:%M')
                    )
                    
                    if start_datetime >= end_datetime:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'End date must be after start date'
                        })

                    # Check driver availability
                    overlapping_bookings = DriverBooking.objects.filter(
                        driver=driver,
                        status__in=['confirmed', 'pending'],
                        payment_status='paid',
                        start_date__lt=end_datetime,
                        end_date__gt=start_datetime
                    )

                    # If vehicle is specified, also check vehicle availability
                    vehicle_id = request.POST.get('vehicle_id')
                    if vehicle_id:
                        try:
                            vehicle = Vehicle.objects.get(id=vehicle_id, status='available')
                            vehicle_overlapping = DriverBooking.objects.filter(
                                vehicle=vehicle,
                                status__in=['confirmed', 'pending'],
                                payment_status='paid',
                                start_date__lt=end_datetime,
                                end_date__gt=start_datetime
                            ).exists()
                            
                            if vehicle_overlapping:
                                return JsonResponse({
                                    'status': 'error',
                                    'available': False,
                                    'message': 'Selected vehicle is not available for these dates'
                                })
                        except Vehicle.DoesNotExist:
                            return JsonResponse({
                                'status': 'error',
                                'message': 'Invalid vehicle selected'
                            })
                except ValueError as e:
                    logger.error(f"Date parsing error in availability check: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid date format. Please use YYYY-MM-DD HH:mm format'
                    })

            else:  # point_to_point
                service_date = request.POST.get('service_date')
                if not service_date:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please provide service date'
                    })

                service_date = timezone.datetime.strptime(service_date, '%Y-%m-%d').date()
                overlapping_bookings = DriverBooking.objects.filter(
                    driver=driver,
                    status__in=['confirmed', 'pending'],
                    payment_status='paid',
                    service_date=service_date
                )

            if overlapping_bookings.exists():
                message = "This time slot is not available. "
                if booking_type == 'specific_date':
                    available_slots = get_available_time_slots(driver, booking_date)
                    if available_slots:
                        message += f"Available slots: {', '.join(available_slots)}"
                    else:
                        message += "No available slots for this date."
                else:
                    next_available = get_next_available_date(driver, booking_type)
                    message += f"Next available date is {next_available.strftime('%Y-%m-%d')}"

                return JsonResponse({
                    'status': 'error',
                    'available': False,
                    'message': message
                })

            return JsonResponse({
                'status': 'success',
                'available': True,
                'message': 'Driver is available for selected time slot'
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

def get_available_time_slots(driver, date):
    # Define available time slots (e.g., 2-hour blocks from 8 AM to 8 PM)
    all_slots = [
        ('08:00', '10:00'), ('10:00', '12:00'), ('12:00', '14:00'),
        ('14:00', '16:00'), ('16:00', '18:00'), ('18:00', '20:00')
    ]
    
    # Get booked slots for the date
    booked_slots = DriverBooking.objects.filter(
        driver=driver,
        booking_type='specific_date',
        booking_date=date,
        status__in=['confirmed', 'pending'],
        payment_status='paid'
    ).values_list('start_time', 'end_time')
    
    # Filter out available slots
    available_slots = []
    for start, end in all_slots:
        slot_start = timezone.datetime.strptime(start, '%H:%M').time()
        slot_end = timezone.datetime.strptime(end, '%H:%M').time()
        
        is_available = True
        for booked_start, booked_end in booked_slots:
            if (slot_start < booked_end and slot_end > booked_start):
                is_available = False
                break
        
        if is_available:
            available_slots.append(f"{start}-{end}")
    
    return available_slots

def get_next_available_date(driver, booking_type):
    today = timezone.now().date()
    next_date = today
    
    while True:
        if booking_type == 'point_to_point':
            has_booking = DriverBooking.objects.filter(
                driver=driver,
                booking_type='point_to_point',
                service_date=next_date,
                status__in=['confirmed', 'pending'],
                payment_status='paid'
            ).exists()
        else:
            has_booking = DriverBooking.objects.filter(
                driver=driver,
                booking_type='with_vehicle',
                start_date__date__lte=next_date,
                end_date__date__gte=next_date,
                status__in=['confirmed', 'pending'],
                payment_status='paid'
            ).exists()
        
        if not has_booking:
            return next_date
        
        next_date += timezone.timedelta(days=1)

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
        return render(request, 'mainapp/booking_list.html', context)
    except Exception as e:
        messages.error(request, 'Error retrieving your bookings')
        return redirect('home')
