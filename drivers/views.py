from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import DriverRegistrationForm, DriverLoginForm
from .models import Driver, DriverDocument, DriverApplicationLog, DriverAuth, DriverTrip, DriverBooking, Vehicle, DriverLocation
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
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

# Create a logger for the drivers app
logger = logging.getLogger(__name__)

# Create your views here.

def driver_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        driver_id = request.session.get('driver_id')
        # Add debug logging
        logger.debug(f"Checking driver_login_required for {request.path}")
        logger.debug(f"Session data: {request.session.items()}")
        logger.debug(f"Driver ID in session: {driver_id}")
        
        if not driver_id:
            messages.error(request, 'Please login first')
            # Store the URL the user was trying to visit
            request.session['next'] = request.get_full_path()
            logger.debug(f"Redirecting to login page, next={request.get_full_path()}")
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
        
        # Get current active trip if any
        active_trip = DriverTrip.objects.filter(
            driver=driver,
            status='started',
            is_tracking_active=True
        ).first()
            
        context = {
            'driver': driver,
            'status': driver.get_status_display(),
            'is_approved': driver.status == 'approved',
            'total_trips': total_trips,
            'driver_bookings': recent_bookings,
            'active_trip': active_trip
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
        
        # Base query for all driver trips
        trips_query = DriverTrip.objects.filter(driver=driver)
        
        # Get current active trip if any
        active_trip = DriverTrip.objects.filter(
            driver=driver,
            status='started'
        ).first()
        
        # Order trips by most recent first, with null start_time at the end
        trips = trips_query.order_by(models.F('start_time').desc(nulls_last=True))
        
        # Add extra data for display
        for trip in trips:
            # Try to get associated booking details
            try:
                booking = DriverBooking.objects.get(id=trip.booking_id)
                trip.user = booking.user
                trip.booking_id = booking.id
                trip.created_at = booking.created_at
                
                # Add location info based on booking type
                if booking.booking_type == 'specific_date':
                    trip.date = booking.booking_date
                    trip.time = booking.start_time
                    trip.location = booking.pickup_location or "Not specified"
                    trip.duration = get_duration_hours(booking.start_time, booking.end_time)
                elif booking.booking_type == 'point_to_point':
                    trip.date = booking.service_date
                    trip.time = None  # No specific time for point-to-point
                    trip.location = f"From: {booking.pickup_location} To: {booking.drop_location}"
                    trip.duration = "Point-to-Point"
                else:  # with_vehicle
                    trip.date = booking.start_date
                    trip.time = booking.start_date.time() if booking.start_date else None
                    trip.location = booking.pickup_location or "Not specified"
                    trip.duration = get_duration_days(booking.start_date, booking.end_date)
                
                trip.amount = booking.amount
            except DriverBooking.DoesNotExist:
                # Handle missing booking
                trip.user = None
                trip.created_at = trip.start_time or timezone.now()
                trip.date = trip.start_time.date() if trip.start_time else timezone.now().date()
                trip.time = trip.start_time.time() if trip.start_time else timezone.now().time()
                trip.location = trip.start_location or "Unknown"
                trip.duration = "Unknown"
                trip.amount = 0
        
        context = {
            'driver': driver,
            'trips': trips,
            'active_trip': active_trip,
            'active_page': 'trips'
        }
        return render(request, 'drivers/trips.html', context)
    except Exception as e:
        logger.error(f"Error in driver_trips view: {str(e)}")
        messages.error(request, 'An error occurred while loading trips')
        return redirect('drivers:dashboard')

def get_duration_hours(start_time, end_time):
    """Calculate duration in hours between two time objects"""
    if not start_time or not end_time:
        return "N/A"
    
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    
    # Handle next day case
    if end_minutes < start_minutes:
        end_minutes += 24 * 60
    
    duration_minutes = end_minutes - start_minutes
    hours = duration_minutes / 60
    
    return f"{hours:.1f}"

def get_duration_days(start_date, end_date):
    """Calculate duration in days between two datetime objects"""
    if not start_date or not end_date:
        return "N/A"
    
    delta = end_date - start_date
    days = delta.days + (delta.seconds / 86400)  # include partial days
    
    return f"{days:.1f} days"

@driver_login_required
def driver_earnings(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        
        # Get filter parameters
        month = request.GET.get('month')
        year = request.GET.get('year')
        
        # Get all completed trips
        completed_trips = DriverTrip.objects.filter(
            driver=driver,
            status='completed'
        ).order_by('-end_time')
        
        # Initialize earnings data
        total_earnings = 0
        monthly_earnings = 0
        total_profit = 0
        monthly_profit = 0
        
        # Current month and year
        current_date = timezone.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # Define profit percentage (80% of amount is profit)
        profit_percentage = 0.80
        
        # Process earnings from trips
        earnings_list = []
        
        for trip in completed_trips:
            # Skip trips without proper data
            if not trip.end_time:
                continue
                
            # Get associated booking
            try:
                booking = DriverBooking.objects.get(id=trip.booking_id)
                
                # Calculate trip amount
                amount = float(booking.amount or 0)
                
                # Calculate profit (80% of amount is profit)
                profit = amount * profit_percentage
                
                # Create earnings record
                earnings_record = {
                    'trip': trip,
                    'amount': amount,
                    'profit': round(profit, 2),
                    'created_at': trip.end_time,
                    'customer': booking.user
                }
                
                # Add distance information
                if trip.distance_covered:
                    trip.distance = round(float(trip.distance_covered), 2)
                else:
                    trip.distance = 0
                
                # If no customer information is available on the trip, add it from booking
                if not hasattr(trip, 'customer'):
                    trip.customer = booking.user
                    
                earnings_list.append(earnings_record)
                
                # Add to totals
                total_earnings += amount
                total_profit += profit
                
                # Check if this is from the current month
                if trip.end_time.month == current_month and trip.end_time.year == current_year:
                    monthly_earnings += amount
                    monthly_profit += profit
                    
            except DriverBooking.DoesNotExist:
                # Trip without booking, skip it or use minimal data
                pass
        
        # Apply month/year filter if specified
        filtered_earnings = earnings_list
        if month and year:
            try:
                filter_month = int(month)
                filter_year = int(year)
                filtered_earnings = [
                    e for e in earnings_list 
                    if e['created_at'].month == filter_month and e['created_at'].year == filter_year
                ]
            except (ValueError, TypeError):
                pass  # Invalid filter, use all earnings
                
        context = {
            'active_page': 'earnings',
            'driver': driver,
            'total_earnings': round(total_earnings, 2),
            'monthly_earnings': round(monthly_earnings, 2),
            'total_profit': round(total_profit, 2),
            'monthly_profit': round(monthly_profit, 2),
            'earnings': filtered_earnings[:10],  # Show most recent 10 earnings
            'all_earnings_count': len(earnings_list)
        }
        return render(request, 'drivers/earnings.html', context)
    except Exception as e:
        logger.error(f"Error in earnings view: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'An error occurred while loading earnings data')
        return redirect('drivers:dashboard')

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

def start_trip(request, booking_id):
    # Check if driver is logged in directly
    driver_id = request.session.get('driver_id')
    logger.debug(f"Session data in start_trip: {request.session.items()}")
    logger.debug(f"Driver ID in session: {driver_id}")
    
    if not driver_id:
        messages.error(request, 'Please login first')
        # Store the URL the user was trying to visit
        request.session['next'] = request.get_full_path()
        logger.debug(f"Redirecting to login page, next={request.get_full_path()}")
        return redirect('drivers:driver_login')
        
    try:
        # Get the booking and verify it belongs to the driver
        driver = Driver.objects.get(id=driver_id)
        booking = get_object_or_404(DriverBooking, id=booking_id)
        
        if booking.driver.id != driver.id:
            messages.error(request, 'Unauthorized: This booking does not belong to you')
            return redirect('drivers:customer_bookings')
        
        # Check if the trip can be started
        if booking.status != 'confirmed':
            messages.error(request, 'Booking is not in confirmed status')
            return redirect('drivers:customer_bookings')
        
        # Check if there's already a trip in progress
        if DriverTrip.objects.filter(driver=driver, status='started').exists():
            messages.error(request, 'You already have a trip in progress')
            return redirect('drivers:customer_bookings')
            
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Check if trip already exists
        trip = DriverTrip.objects.filter(driver=driver, booking_id=booking.id).first()
        
        if not trip:
            # Create a new trip with 'assigned' status
            trip = DriverTrip.objects.create(
                driver=driver,
                booking_id=booking.id,
                status='assigned',
                start_location='Pickup location',  # Will be updated when trip actually starts
                end_location='To be determined',
                otp=otp,
            )
        else:
            # Update existing trip with new OTP
            trip.otp = otp
            trip.otp_verified = False
            trip.save()
        
        # Store OTP in session with timestamp and attempt counter
        request.session[f'trip_otp_{booking_id}'] = {
            'otp': otp,
            'timestamp': timezone.now().timestamp(),
            'attempts': 0
        }
        
        # Prepare email content
        context = {
            'user_name': booking.user.get_full_name() or booking.user.username,
            'otp': otp,
            'booking': booking,
            'driver_name': driver.full_name,
            'trip_details': booking.get_booking_details(),
            'otp_expiry_minutes': 10  # OTP expires after 10 minutes
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
            messages.success(request, f"OTP sent to customer at {booking.user.email}. Please ask them to check their email.")
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            messages.error(request, 'Failed to send OTP email. Please try again.')
            return redirect('drivers:customer_bookings')
        
        # Redirect to the OTP verification page
        return redirect('drivers:verify_trip_otp', booking_id=booking_id)
        
    except Exception as e:
        logger.error(f"Error in start_trip: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'An error occurred while starting the trip.')
        return redirect('drivers:customer_bookings')

def verify_trip_otp(request, booking_id):
    # Check if driver is logged in directly
    driver_id = request.session.get('driver_id')
    logger.debug(f"Session data in verify_trip_otp: {request.session.items()}")
    logger.debug(f"Driver ID in session: {driver_id}")
    
    if not driver_id:
        messages.error(request, 'Please login first')
        # Store the URL the user was trying to visit
        request.session['next'] = request.get_full_path()
        logger.debug(f"Redirecting to login page, next={request.get_full_path()}")
        return redirect('drivers:driver_login')
    
    try:
        # Get the driver and booking
        driver = Driver.objects.get(id=driver_id)
        booking = get_object_or_404(DriverBooking, id=booking_id)
        
        # Verify booking belongs to this driver
        if booking.driver.id != driver.id:
            messages.error(request, 'Unauthorized: This booking does not belong to you')
            return redirect('drivers:customer_bookings')
            
        if request.method == 'POST':
            otp = request.POST.get('otp')
            if not otp:
                messages.error(request, 'OTP is required')
                return render(request, 'drivers/verify_otp.html', {'booking': booking})
                
            # Get location data if available
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            accuracy = request.POST.get('accuracy')
            
            # Get stored OTP data
            stored_otp_data = request.session.get(f'trip_otp_{booking_id}')
            if not stored_otp_data:
                messages.error(request, 'OTP has expired. Please request a new one.')
                return render(request, 'drivers/verify_otp.html', {'booking': booking})
                
            # Check OTP expiration (10 minutes)
            current_time = timezone.now().timestamp()
            if current_time - stored_otp_data['timestamp'] > 600:  # 10 minutes
                del request.session[f'trip_otp_{booking_id}']
                messages.error(request, 'OTP has expired. Please request a new one.')
                return render(request, 'drivers/verify_otp.html', {'booking': booking})
                
            # Check attempts
            if stored_otp_data['attempts'] >= 3:
                del request.session[f'trip_otp_{booking_id}']
                messages.error(request, 'Too many attempts. Please request a new OTP.')
                return render(request, 'drivers/verify_otp.html', {'booking': booking})
                
            # Increment attempts
            stored_otp_data['attempts'] += 1
            request.session[f'trip_otp_{booking_id}'] = stored_otp_data
            
            # Verify OTP
            if otp != stored_otp_data['otp']:
                messages.error(request, f'Invalid OTP. {3 - stored_otp_data["attempts"]} attempts remaining.')
                return render(request, 'drivers/verify_otp.html', {'booking': booking})
                
            # Get or create trip
            trip, created = DriverTrip.objects.get_or_create(
                booking_id=booking.id,
                defaults={
                    'driver': driver,
                    'status': 'assigned',
                    'start_location': booking.pickup_location or 'Trip start location',
                    'end_location': booking.drop_location or 'Trip end location',
                    'otp': stored_otp_data['otp'],
                    'otp_verified': True
                }
            )
            
            # Update existing trip and start it
            trip.otp_verified = True
            
            # Convert start location coordinates if available
            start_location = booking.pickup_location or 'Trip start location'
            start_lat = None
            start_lng = None
            
            if latitude and longitude:
                start_lat = float(latitude)
                start_lng = float(longitude)
            elif booking.pickup_latitude and booking.pickup_longitude:
                start_lat = booking.pickup_latitude
                start_lng = booking.pickup_longitude
            
            # Start the trip
            trip.start(start_location=start_location, lat=start_lat, lng=start_lng)
            
            # Update booking status
            booking.status = 'in_progress'
            booking.save()
            
            # Clear OTP from session
            del request.session[f'trip_otp_{booking_id}']
            
            # Send trip start notification to the customer
            try:
                send_trip_start_notification(booking, trip)
            except Exception as e:
                logger.error(f"Failed to send trip start notification: {str(e)}")
                # Continue even if notification fails
            
            messages.success(request, 'Trip started successfully!')
            return redirect('drivers:view_active_trip', trip_id=trip.id)
        
        # If GET request, show the OTP verification form
        return render(request, 'drivers/verify_otp.html', {
            'booking': booking,
            'driver': driver
        })
        
    except Exception as e:
        logger.error(f"Error in verify_trip_otp: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'An error occurred while verifying OTP')
        return redirect('drivers:customer_bookings')

@driver_login_required
def end_trip(request, booking_id):
    try:
        booking = get_object_or_404(DriverBooking, id=booking_id)
        driver = Driver.objects.get(id=request.session['driver_id'])
        
        # Security check
        if booking.driver.id != driver.id:
            messages.error(request, 'Unauthorized access')
            return redirect('drivers:customer_bookings')
        
        # Get trip
        trip = DriverTrip.objects.filter(booking_id=booking.id).first()
        if not trip:
            messages.error(request, 'No active trip found for this booking')
            return redirect('drivers:customer_bookings')
        
        if not trip.can_end():
            messages.error(request, 'This trip cannot be ended at this time')
            return redirect('drivers:customer_bookings')
        
        
        if request.method == 'POST':
            # Get location data
            end_location = request.POST.get('end_location', '')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            # Set end location
            end_lat = None
            end_lng = None
            
            if latitude and longitude:
                end_lat = float(latitude)
                end_lng = float(longitude)
            elif booking.drop_latitude and booking.drop_longitude:
                end_lat = booking.drop_latitude
                end_lng = booking.drop_longitude
            
            # End the trip
            with transaction.atomic():
                trip.end(end_location=end_location or booking.drop_location or 'Trip end location', 
                         lat=end_lat, lng=end_lng)
                
                # Update booking status
                booking.status = 'completed'
                booking.save()
                
                # Update driver status
                driver.availability_status = 'available'
                driver.save()
            
            # Send trip completion notification
            try:
                send_trip_completion_notification(booking, trip)
            except Exception as e:
                logger.error(f"Failed to send trip completion notification: {str(e)}")
                # Continue even if notification fails
            
            messages.success(request, 'Trip completed successfully')
            return redirect('drivers:completed_trips')
        
        # If GET request, show the end trip form
        context = {
            'driver': driver,
            'booking': booking,
            'trip': trip,
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
        }
        return render(request, 'drivers/end_trip.html', context)
        
    except Exception as e:
        logger.error(f"Error ending trip: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, f'Error ending trip: {str(e)}')
        return redirect('drivers:customer_bookings')

def send_trip_start_notification(booking, trip):
    """Send notification that trip has started"""
    subject = 'Your Trip Has Started'
    context = {
        'user_name': booking.user.get_full_name() or booking.user.username,
        'booking': booking,
        'trip': trip,
        'driver_name': booking.driver.full_name,
        'start_time': trip.start_time.strftime('%I:%M %p, %b %d, %Y')
    }
    
    html_message = render_to_string('drivers/email/trip_started.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.user.email],
        html_message=html_message,
        fail_silently=False
    )
    
    logger.info(f"Trip start notification sent to {booking.user.email} for trip {trip.id}")

def send_trip_completion_notification(booking, trip):
    """Send notification that trip has completed"""
    subject = 'Your Trip Has Completed'
    context = {
        'user_name': booking.user.get_full_name() or booking.user.username,
        'booking': booking,
        'trip': trip,
        'driver_name': booking.driver.full_name,
        'start_time': trip.start_time.strftime('%I:%M %p, %b %d, %Y'),
        'end_time': trip.end_time.strftime('%I:%M %p, %b %d, %Y'),
        'distance': trip.distance_covered,
        'duration': (trip.end_time - trip.start_time).total_seconds() // 60,  # Duration in minutes
        'feedback_url': f"/drivers/feedback/{trip.id}/"
    }
    
    html_message = render_to_string('drivers/email/trip_completed.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.user.email],
        html_message=html_message,
        fail_silently=False
    )
    
    logger.info(f"Trip completion notification sent to {booking.user.email} for trip {trip.id}")

@driver_login_required
def completed_trips(request):
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        
        # Get filter parameters
        date = request.GET.get('date')
        search = request.GET.get('search')
        
        # Get completed trips
        trips_query = DriverTrip.objects.filter(
            driver=driver,
            status='completed'
        )
        
        # Apply filters
        if date:
            try:
                filter_date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
                trips_query = trips_query.filter(
                    models.Q(start_time__date=filter_date) | 
                    models.Q(end_time__date=filter_date)
                )
            except ValueError:
                pass  # Invalid date format, ignore filter
        
        if search:
            # Search by trip ID or related booking details
            trips_query = trips_query.filter(
                models.Q(id__icontains=search) |
                models.Q(booking_id__icontains=search)
            )
        
        # Order by most recent completion first
        completed_trips = trips_query.order_by('-end_time')
        
        # Get current active trip if any
        active_trip = DriverTrip.objects.filter(
            driver=driver,
            status='started'
        ).first()
        
        # Add extra data for display
        for trip in completed_trips:
            # Calculate trip metrics
            if trip.start_time and trip.end_time:
                trip_duration = trip.end_time - trip.start_time
                trip.duration_hours = round(trip_duration.total_seconds() / 3600, 1)
            else:
                trip.duration_hours = 0
                
            # Try to get associated booking details
            try:
                booking = DriverBooking.objects.get(id=trip.booking_id)
                trip.user = booking.user
                trip.booking_id = booking.id
                trip.created_at = booking.created_at
                
                # Add location info based on booking type
                if booking.booking_type == 'specific_date':
                    trip.date = booking.booking_date
                    trip.time = booking.start_time
                    trip.location = booking.pickup_location or "Not specified"
                    trip.duration = f"{trip.duration_hours} hours"
                elif booking.booking_type == 'point_to_point':
                    trip.date = booking.service_date
                    trip.time = None
                    trip.location = f"From: {booking.pickup_location} To: {booking.drop_location}"
                    trip.duration = f"{trip.duration_hours} hours"
                else:  # with_vehicle
                    trip.date = booking.start_date
                    trip.time = booking.start_date.time() if booking.start_date else None
                    trip.location = booking.pickup_location or "Not specified"
                    if booking.start_date and booking.end_date:
                        days = (booking.end_date - booking.start_date).days + 1
                        trip.duration = f"{days} days"
                    else:
                        trip.duration = f"{trip.duration_hours} hours"
                
                trip.amount = booking.amount
                
            except DriverBooking.DoesNotExist:
                # Handle missing booking
                trip.user = None
                trip.created_at = trip.start_time or timezone.now()
                trip.date = trip.end_time.date() if trip.end_time else timezone.now().date()
                trip.time = trip.start_time.time() if trip.start_time else timezone.now().time()
                trip.location = f"{trip.start_location} to {trip.end_location}"
                trip.duration = f"{trip.duration_hours} hours"
                trip.amount = 0
        
        context = {
            'driver': driver,
            'trips': completed_trips,
            'active_trip': active_trip,
            'active_page': 'completed_trips',
            'date': date,
            'search': search
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

@require_http_methods(["POST"])
@csrf_exempt
def update_location(request, trip_id):
    """Update driver location during a trip"""
    # Check if driver is logged in directly
    driver_id = request.session.get('driver_id')
    logger.debug(f"Session data in update_location: {request.session.items()}")
    logger.debug(f"Driver ID in session: {driver_id}")
    
    if not driver_id:
        return JsonResponse({'status': 'error', 'message': 'Please login first'}, status=401)
        
    try:
        # Get the trip
        trip = get_object_or_404(DriverTrip, id=trip_id)
        driver = Driver.objects.get(id=driver_id)
        
        # Security check
        if trip.driver.id != driver.id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized access'}, status=403)
        
        # Check if trip is active
        if trip.status != 'started' or not trip.is_tracking_active:
            return JsonResponse({'status': 'error', 'message': 'Trip is not active'}, status=400)
        
        # Get location data
        try:
            latitude = float(request.POST.get('latitude'))
            longitude = float(request.POST.get('longitude'))
            
            # Optional fields
            accuracy = request.POST.get('accuracy')
            speed = request.POST.get('speed')
            heading = request.POST.get('heading')
            
            if accuracy:
                accuracy = float(accuracy)
            if speed:
                speed = float(speed)
            if heading:
                heading = float(heading)
                
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid location data'}, status=400)
        
        # Create location record
        location = DriverLocation.objects.create(
            driver=driver,
            trip=trip,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy or 0,
            speed=speed or 0,
            heading=heading or 0
        )
        
        # Update trip's route data
        if trip.route_data:
            route_data = trip.route_data
        else:
            route_data = []
            
        route_data.append({
            'lat': latitude,
            'lng': longitude,
            'time': timezone.now().timestamp(),
            'speed': speed or 0
        })
        
        trip.route_data = route_data
        trip.save(update_fields=['route_data'])
        
        return JsonResponse({
            'status': 'success',
            'message': 'Location updated',
            'location_id': location.id
        })
        
    except Exception as e:
        logger.error(f"Error updating location: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while updating location'
        }, status=500)

def view_active_trip(request, trip_id):
    """View details of an active trip with real-time tracking"""
    # Check if driver is logged in directly
    driver_id = request.session.get('driver_id')
    logger.debug(f"Session data in view_active_trip: {request.session.items()}")
    logger.debug(f"Driver ID in session: {driver_id}")
    
    if not driver_id:
        messages.error(request, 'Please login first')
        # Store the URL the user was trying to visit
        request.session['next'] = request.get_full_path()
        logger.debug(f"Redirecting to login page, next={request.get_full_path()}")
        return redirect('drivers:driver_login')
        
    try:
        trip = get_object_or_404(DriverTrip, id=trip_id, status='started')
        driver = Driver.objects.get(id=driver_id)
        
        # Security check - ensure this trip belongs to the logged-in driver
        if trip.driver.id != driver.id:
            messages.error(request, 'You do not have permission to view this trip')
            return redirect('drivers:customer_bookings')
        
        # Get the associated booking - use booking_id directly
        try:
            booking = DriverBooking.objects.get(id=trip.booking_id)
        except DriverBooking.DoesNotExist:
            booking = None
        
        context = {
            'driver': driver,
            'trip': trip,
            'booking': booking,
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
            'active_page': 'active_trips'
        }
        
        return render(request, 'drivers/active_trip.html', context)
        
    except Exception as e:
        logger.error(f"Error viewing active trip: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'An error occurred while loading the trip')
        return redirect('drivers:customer_bookings')

@driver_login_required
def customer_bookings(request):
    """View all customer bookings for this driver with notifications for upcoming trips and ongoing trips"""
    try:
        driver = Driver.objects.get(id=request.session['driver_id'])
        
        # Get current date and time
        current_datetime = timezone.now()
        
        # Get active trips for this driver
        active_trips = DriverTrip.objects.filter(
            driver=driver,
            status='started'
        ).order_by('-start_time')
        
        # Get associated bookings for active trips
        active_trip_bookings = []
        booked_trip_ids = []
        
        for trip in active_trips:
            try:
                booking = DriverBooking.objects.get(id=trip.booking_id)
                active_trip_bookings.append({
                    'trip': trip,
                    'booking': booking
                })
                booked_trip_ids.append(trip.booking_id)
                logger.debug(f"Found active trip for booking {booking.id}")
            except DriverBooking.DoesNotExist:
                logger.warning(f"No booking found for trip {trip.id} with booking_id {trip.booking_id}")
                active_trip_bookings.append({
                    'trip': trip,
                    'booking': None
                })
        
        # Get all confirmed bookings for this driver that are not already active
        bookings = DriverBooking.objects.filter(
            driver=driver,
            status='confirmed',
            payment_status='paid'
        ).exclude(
            id__in=booked_trip_ids
        ).order_by('service_date', 'start_date', 'booking_date')
        
        # Get current active trip if any
        active_trip = DriverTrip.objects.filter(
            driver=driver,
            status='started'
        ).first()
        
        # Process bookings to add notification flags for upcoming trips
        processed_bookings = []
        has_upcoming_bookings = False
        
        # Calendar bookings for the next 3 days
        calendar_bookings = {}
        
        for booking in bookings:
            # Determine if the trip is ready to start
            is_ready_to_start = False
            is_upcoming = False
            time_until_start = None
            calendar_date = None
            
            if booking.booking_type == 'specific_date':
                if booking.booking_date and booking.start_time:
                    booking_datetime = datetime.combine(
                        booking.booking_date,
                        booking.start_time
                    ).replace(tzinfo=timezone.get_current_timezone())
                    
                    calendar_date = booking.booking_date
                    
                    # Ready to start if the start time is now or has passed
                    is_ready_to_start = current_datetime >= booking_datetime
                    
                    # Upcoming if within 24 hours
                    time_diff = booking_datetime - current_datetime
                    is_upcoming = time_diff.total_seconds() > 0 and time_diff.total_seconds() <= 86400  # 24 hours
                    
                    if is_upcoming:
                        has_upcoming_bookings = True
                        hours = int(time_diff.total_seconds() // 3600)
                        minutes = int((time_diff.total_seconds() % 3600) // 60)
                        time_until_start = f"{hours}h {minutes}m"
                    
            elif booking.booking_type == 'point_to_point':
                if booking.service_date:
                    calendar_date = booking.service_date
                    
                    # Ready to start if service date is today or has passed
                    is_ready_to_start = current_datetime.date() >= booking.service_date
                    
                    # Upcoming if service date is tomorrow
                    try:
                        is_upcoming = (booking.service_date - current_datetime.date()).days <= 1
                        if is_upcoming:
                            has_upcoming_bookings = True
                    except (TypeError, ValueError):
                        is_upcoming = False
                else:
                    is_ready_to_start = False
                    is_upcoming = False
            
            elif booking.booking_type == 'with_vehicle':
                if booking.start_date:
                    try:
                        calendar_date = booking.start_date.date()
                        
                        # Ready to start if start date has arrived
                        is_ready_to_start = current_datetime >= booking.start_date
                        
                        # Upcoming if within 24 hours
                        time_diff = booking.start_date - current_datetime
                        is_upcoming = time_diff.total_seconds() > 0 and time_diff.total_seconds() <= 86400  # 24 hours
                        
                        if is_upcoming:
                            has_upcoming_bookings = True
                            hours = int(time_diff.total_seconds() // 3600)
                            minutes = int((time_diff.total_seconds() % 3600) // 60)
                            time_until_start = f"{hours}h {minutes}m"
                    except (TypeError, ValueError, AttributeError):
                        is_ready_to_start = False
                        is_upcoming = False
                        calendar_date = None
                else:
                    is_ready_to_start = False
                    is_upcoming = False
                    calendar_date = None
            
            # Create a booking item
            booking_item = {
                'booking': booking,
                'is_ready_to_start': is_ready_to_start,
                'is_upcoming': is_upcoming,
                'time_until_start': time_until_start
            }
            
            # Add to processed bookings
            processed_bookings.append(booking_item)
            
            # Add to calendar if in the next 3 days
            if calendar_date:
                try:
                    days_difference = (calendar_date - current_datetime.date()).days
                    if 0 <= days_difference <= 3:
                        if calendar_date not in calendar_bookings:
                            calendar_bookings[calendar_date] = []
                        calendar_bookings[calendar_date].append(booking_item)
                except (TypeError, ValueError):
                    # Skip this booking for calendar if the date calculation fails
                    pass
        
        # Sort calendar bookings by date
        calendar_bookings = dict(sorted(calendar_bookings.items()))
        
        context = {
            'driver': driver,
            'bookings': processed_bookings,
            'active_trip': active_trips.first(),  # For backward compatibility
            'active_trips': active_trips,
            'active_trip_bookings': active_trip_bookings,
            'has_active_trips': len(active_trip_bookings) > 0,
            'active_page': 'customer_bookings',
            'current_datetime': current_datetime,
            'has_upcoming_bookings': has_upcoming_bookings,
            'calendar_bookings': calendar_bookings
        }
        
        return render(request, 'drivers/customer_bookings.html', context)
    
    except Exception as e:
        logger.error(f"Error viewing customer bookings: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'An error occurred while loading bookings')
        return redirect('drivers:dashboard')
