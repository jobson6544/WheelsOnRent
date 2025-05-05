from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from .forms import UserRegistrationForm, UserProfileForm, UserEditForm, UserProfileEditForm, FeedbackForm
from .models import UserProfile, Booking, User, Feedback, LocationShare, AccidentReport, BookingExtension
from vendor.models import Vehicle
from drivers.models import Driver, DriverBooking
from datetime import datetime, timedelta
import logging
import stripe
from .utils import generate_verification_token
from django.contrib.sites.shortcuts import get_current_site
import traceback
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
import json  # Also make sure this is imported
from openai import OpenAI
import os
from django.db.models import Avg
from decimal import Decimal
import random

User = get_user_model()

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# Initialize OpenAI client with GitHub model configuration
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)

def index(request):
    return render(request, 'mainapp/index.html')

def customer_register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'user'
            user.is_active = False  # Deactivate account till it is verified
            user.email_verification_token = generate_verification_token()
            user.save()

            # Send verification email
            current_site = get_current_site(request)
            mail_subject = 'Activate your account'
            message = render_to_string('emails/email_verification.html', {
                'user': user,
                'domain': current_site.domain,
                'token': user.email_verification_token,
            })
            plain_message = strip_tags(message)
            to_email = form.cleaned_data.get('email')
            send_mail(mail_subject, plain_message, settings.DEFAULT_FROM_EMAIL, [to_email], html_message=message)

            messages.success(request, 'Please check your email to verify your account.')
            return redirect('login')  # Redirect to login page after registration
    else:
        form = UserRegistrationForm()
    return render(request, 'mainapp/register.html', {'form': form})

def verify_email(request, token):
    try:
        user = User.objects.get(email_verification_token=token)
        if user.is_email_verified:
            messages.info(request, 'Email already verified.')
        else:
            user.is_email_verified = True
            user.is_active = True
            user.email_verification_token = None
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Your email has been verified. Your account is now active.')
        return redirect('login')
    except User.DoesNotExist:
        messages.error(request, 'Invalid verification link')
        return redirect('login')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.is_email_verified:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                if hasattr(user, 'is_first_login') and user.is_first_login:
                    user.is_first_login = False
                    user.save()
                    return redirect('mainapp:complete_profile')
                return redirect('mainapp:home')
            else:
                messages.error(request, "Please verify your email before logging in.")
        else:
            messages.error(request, "Invalid email or password.")
    return render(request, 'mainapp/user_login.html')

@login_required(login_url='login')
def complete_profile(request):
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Check if profile is already complete
        if profile.is_complete and not request.user.is_first_login:
            messages.info(request, "Your profile is already complete.")
            return redirect('mainapp:home')

        if request.method == 'POST':
            form = UserProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                profile = form.save(commit=False)
                profile.is_complete = True
                profile.save()

                # Update user's first login status
                request.user.is_first_login = False
                request.user.save()

                messages.success(request, 'Profile completed successfully!')
                return redirect('mainapp:home')
        else:
            form = UserProfileForm(instance=profile)

        return render(request, 'mainapp/complete_profile.html', {
            'form': form,
            'is_google_user': request.user.auth_method == 'google'
        })
    except Exception as e:
        logger.error(f"Error in complete_profile view: {str(e)}")
        messages.error(request, "An error occurred while loading your profile.")
        return redirect('mainapp:home')

def home(request):
    # Get all vehicles except those explicitly marked as not available
    vehicles = Vehicle.objects.exclude(
        status='not_available'  # Only exclude vehicles marked as not available
    ).select_related(
        'vendor', 
        'model__sub_category__category'
    ).prefetch_related('features')
    
    # Get available drivers who are approved and active
    available_drivers = Driver.objects.filter(
        status='approved',
        availability_status='available',
        auth__is_active=True
    ).select_related(
        'auth'
    ).annotate(
        rating_avg=Avg('driver_bookings__reviews__rating')
    )
    
    context = {
        'vehicles': vehicles,
        'drivers': available_drivers
    }
    
    # Add debug information
    print(f"Number of vehicles found: {vehicles.count()}")
    for vehicle in vehicles:
        print(f"Vehicle: {vehicle.model}, Status: {vehicle.status}, Available: {vehicle.availability}")
    
    return render(request, 'mainapp/home.html', context)

def success(request):
    return render(request, 'mainapp/success.html')

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
    return render(request, 'mainapp/profile.html', context)

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
@login_required
@login_required
@login_required
def book_vehicle(request, id):
    logger.info(f"Booking view called for vehicle id: {id}")
    vehicle = get_object_or_404(Vehicle, id=id)
    
    if request.method == 'POST':
        logger.info("POST request received")
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        logger.info(f"Start date: {start_date_str}, End date: {end_date_str}")
        
        try:
            # Convert strings to datetime objects
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d'))

            # Ensure end_date is at least one day after start_date
            if end_date <= start_date:
                end_date = start_date + timedelta(days=1)

            # Set the time to the start and end of the day
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            logger.info(f"Adjusted dates - Start: {start_date}, End: {end_date}")

            # Check if the vehicle is available for the selected dates
            if not Booking.check_availability(vehicle, start_date, end_date):
                logger.warning("Vehicle is not available for the selected dates.")
                return JsonResponse({
                    'success': False,
                    'message': 'Vehicle is not available for the selected dates. Please choose different dates.'
                })

            logger.info("Vehicle is available for the selected dates.")

            # Calculate the total amount
            duration = (end_date.date() - start_date.date()).days + 1  # Duration in days (inclusive)
            total_amount = duration * vehicle.rental_rate

            # Create the booking
            booking = Booking.objects.create(
                user=request.user,
                vehicle=vehicle,
                start_date=start_date,
                end_date=end_date,
                status='pending',
                total_amount=total_amount
            )
            logger.info(f"Booking created successfully: {booking.booking_id}")

            # Generate and send QR code
            booking.generate_and_send_qr(request)

            messages.success(request, 'Booking created successfully! Check your email for the pickup QR code.')

            # Return JSON response for successful booking
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('mainapp:payment') + f'?booking_id={booking.booking_id}'
            })
        
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while processing your booking. Please try again later.'
            })

    return render(request, 'mainapp/book_vehicle.html', {'vehicle': vehicle})

@login_required
def user_booking_history(request):
    try:
        # Get vehicle bookings
        bookings_list = Booking.objects.filter(user=request.user).order_by('-booking_id')
        paginator = Paginator(bookings_list, 10)  # Show 10 bookings per page
        page = request.GET.get('page')
        try:
            bookings = paginator.page(page)
        except PageNotAnInteger:
            bookings = paginator.page(1)
        except EmptyPage:
            bookings = paginator.page(paginator.num_pages)

        # Get driver bookings
        driver_bookings_list = DriverBooking.objects.filter(
            user=request.user
        ).select_related(
            'driver'  # Include driver details
        ).order_by('-id')
        
        driver_paginator = Paginator(driver_bookings_list, 6)
        driver_page = request.GET.get('driver_page')
        try:
            driver_bookings = driver_paginator.page(driver_page)
        except PageNotAnInteger:
            driver_bookings = driver_paginator.page(1)
        except EmptyPage:
            driver_bookings = driver_paginator.page(driver_paginator.num_pages)
        
        context = {
            'bookings': bookings,
            'driver_bookings': driver_bookings,
            'has_bookings': bookings_list.exists(),
            'has_driver_bookings': driver_bookings_list.exists(),
            'active_tab': request.GET.get('tab', 'vehicles'),
        }
        
        return render(request, 'mainapp/user_booking_history.html', context)
    except Exception as e:
        logger.error(f"Error in user_booking_history: {str(e)}")
        messages.error(request, 'An error occurred while retrieving your bookings. Please try again.')
        return redirect('mainapp:home')

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    
    if request.method == 'POST':
        if booking.status in ['pending', 'confirmed']:
            start_datetime = timezone.make_aware(
                datetime.combine(booking.start_date.date(), booking.start_date.time())
            ) if timezone.is_naive(booking.start_date) else booking.start_date
            
            if start_datetime > timezone.now() + timedelta(hours=24):
                old_status = booking.status
                booking.status = 'cancelled'
                booking.save()
                
                email_sent = send_cancellation_email(booking)
                if not email_sent:
                    messages.warning(request, 'Booking cancelled, but there was an issue sending the confirmation email.')
                
                if old_status == 'confirmed':
                    handle_refund(request, booking)
                else:
                    messages.success(request, 'Your pending booking has been successfully cancelled.')
            else:
                messages.error(request, 'Bookings can only be cancelled more than 24 hours before the start time.')
        else:
            messages.error(request, 'This booking cannot be cancelled.')
    
    return redirect('mainapp:user_booking_history')

def send_cancellation_email(booking):
    subject = 'Booking Cancellation Confirmation'
    html_message = render_to_string('emails/booking_cancellation.html', {
        'booking': booking,
        'user': booking.user,
    })
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = booking.user.email
    logger.info(f"Sending cancellation email to {to_email}")

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send cancellation email for booking {booking.booking_id}: {str(e)}")
        return False

def handle_refund(request, booking):
    if not booking.stripe_payment_intent_id:
        messages.warning(request, 'No payment was processed for this booking. Cancellation completed without refund.')
        booking.refund_status = 'not_applicable'
        booking.save()
        return

    try:
        payment_intent = stripe.PaymentIntent.retrieve(booking.stripe_payment_intent_id)
        
        if payment_intent.status == 'succeeded':
            refund = stripe.Refund.create(
                payment_intent=payment_intent.id,
                amount=int(booking.total_amount * 100)  # Convert to cents
            )
            
            if refund.status == 'succeeded':
                booking.refund_status = 'refunded'
                booking.save()
                messages.success(request, 'Your booking has been cancelled and your payment has been refunded.')
            else:
                booking.refund_status = 'pending'
                booking.save()
                messages.warning(request, 'Your booking has been cancelled. Refund initiated but not yet confirmed. Please check your account in 5-10 business days.')
        else:
            messages.warning(request, 'Your booking has been cancelled. No refund was processed as the payment was not completed.')
    
    except stripe.error.StripeError as e:
        messages.error(request, f'An error occurred while processing your refund: {str(e)}')
        booking.refund_status = 'failed'
        booking.save()

@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, 'mainapp/profile_view.html', {'profile': profile})

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
            return redirect('mainapp:profile_view')
    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = UserProfileEditForm(instance=request.user.profile)
    
    return render(request, 'mainapp/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

def payment_view(request):
    booking_id = request.GET.get('booking_id')
    if not booking_id:
        messages.error(request, "No booking specified for payment.")
        return redirect('home')
    
    booking = get_object_or_404(Booking, booking_id=booking_id, status='pending')
    
    # Calculate the amount based on the booking
    amount = calculate_booking_amount(booking)
    
    if amount <= 0:
        messages.error(request, "Invalid booking amount. Please contact support.")
        return redirect('payment_error')
    
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'inr',
                'unit_amount': int(amount * 100),
                'product_data': {
                    'name': f'Booking {booking.booking_id}',
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.build_absolute_uri(reverse('mainapp:payment_success')) + f'?session_id={{CHECKOUT_SESSION_ID}}&booking_id={booking_id}',
        cancel_url=request.build_absolute_uri(reverse('mainapp:payment_cancelled')) + f'?booking_id={booking_id}',
        client_reference_id=str(booking_id),
    )
    
    booking.stripe_payment_intent_id = session.payment_intent
    booking.save()

    return render(request, 'mainapp/payment.html', {
        'session_id': session.id,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'booking': booking,
    })

def calculate_booking_amount(booking):
    if not booking or not booking.start_date or not booking.end_date or not booking.vehicle:
        return 0  # Return 0 if any required data is missing
    
    # Calculate the number of days
    num_days = (booking.end_date - booking.start_date).days 
    
    # Get the daily rate from the vehicle
    daily_rate = booking.vehicle.rental_rate
    
    if not daily_rate:
        return 0  # Return 0 if the vehicle doesn't have a rental rate
    
    # Calculate the total amount
    total_amount = num_days * daily_rate
    
    return total_amount

@require_GET
def payment_success(request):
    session_id = request.GET.get('session_id')
    booking_id = request.GET.get('booking_id')
    
    if not session_id or not booking_id:
        messages.error(request, "Invalid payment confirmation.")
        return redirect('mainapp:home')
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid" and str(session.client_reference_id) == str(booking_id):
            booking.status = 'confirmed'
            booking.stripe_payment_intent_id = session.payment_intent
            booking.save()
            
            # Send confirmation email
            email_sent = send_booking_confirmation_email(booking)
            if email_sent:
                messages.success(request, "Booking confirmed successfully! A confirmation email has been sent.")
            else:
                messages.success(request, "Booking confirmed successfully! However, there was an issue sending the confirmation email.")
        else:
            messages.warning(request, "Payment was successful, but booking confirmation failed. Please contact support.")
    except stripe.error.StripeError as e:
        messages.error(request, f"An error occurred while confirming your booking: {str(e)}")
        booking.status = 'payment_failed'
        booking.save()
    
    return render(request, 'mainapp/payment_success.html', {'booking': booking})

def send_booking_confirmation_email(booking):
    subject = 'Booking Confirmation'
    html_message = render_to_string('emails/booking_confirmation.html', {
        'booking': booking,
        'user': booking.user,
    })
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = booking.user.email

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Confirmation email sent for booking {booking.booking_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email for booking {booking.booking_id}: {str(e)}")
        return False

def payment_cancelled(request):
    booking_id = request.GET.get('booking_id')
    if booking_id:
        booking = get_object_or_404(Booking, booking_id=booking_id)
        booking.status = 'cancelled'
        booking.save()
        messages.warning(request, "Your booking has been cancelled.")
    return render(request, 'mainapp/payment_cancelled.html')

def payment_error(request):
    return render(request, 'mainapp/payment_error.html')

def vendor_benefits(request):
    benefits = [
        "Increased revenue through our wide customer base",
        "Flexible rental options to suit your needs",
        "Secure and insured transactions",
        "Easy-to-use platform for managing your listings",
        "24/7 customer support"
    ]
    
    context = {
        'benefits': benefits,
        'max_days': 30,  # Maximum number of days for the scrollbar
    }
    
    if request.method == 'POST':
        rental_days = int(request.POST.get('rental_days', 0))
        rental_price = float(request.POST.get('rental_price', 0))
        
        # Calculate profits for all days up to rental_days
        total_prices = [day * rental_price for day in range(1, rental_days + 1)]
        wheels_on_rent_fees = [price * 0.1 for price in total_prices]
        vendor_profits = [price - fee for price, fee in zip(total_prices, wheels_on_rent_fees)]
        
        return JsonResponse({
            'total_prices': total_prices,
            'wheels_on_rent_fees': wheels_on_rent_fees,
            'vendor_profits': vendor_profits
        })
    
    return render(request, 'mainapp/vendor_benefits.html', context)

@require_http_methods(["GET", "POST"])
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, is_active=True, role='user')
            if user.is_email_verified:
                token = user.generate_password_reset_token()
                reset_url = request.build_absolute_uri(reverse('mainapp:password_reset_verify'))
                send_mail(
                    'Password Reset OTP',
                    f'Your OTP for password reset is: {token}\nUse this OTP at {reset_url}',
                    'from@example.com',
                    [user.email],
                    fail_silently=False,
                )
                return JsonResponse({'status': 'success', 'message': 'A password reset OTP has been sent to your email.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Your email is not verified. Please verify your email first.'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'No active customer account found with this email address.'})
    return render(request, 'mainapp/forgot_password.html')

@require_http_methods(["GET", "POST"])
def password_reset_verify(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        token = request.POST.get('token')
        new_password = request.POST.get('new_password')
        try:
            user = User.objects.get(email=email, is_active=True, role='user')
            if user.is_email_verified and user.password_reset_token == token and user.is_password_reset_token_valid():
                user.set_password(new_password)
                user.password_reset_token = None
                user.password_reset_token_created_at = None
                user.save()
                return JsonResponse({'status': 'success', 'message': 'Your password has been reset successfully. You can now login with your new password.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP. Please try again.'})
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'No active customer account found with this email address.'})
    return render(request, 'mainapp/password_reset_verify.html')

@login_required
def user_bookings(request):
    bookings_list = Booking.objects.filter(user=request.user).order_by('-start_date')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(bookings_list, 10)  # Show 10 bookings per page
    
    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)
    
    context = {
        'bookings': bookings,
    }
    return render(request, 'mainapp/user_bookings.html', context)

@login_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    vehicle_details = booking.get_vehicle_details()
    vendor_details = booking.get_vendor_details()
    
    context = {
        'booking': booking,
        'vehicle_details': vehicle_details,
        'vendor_details': vendor_details,
        'can_submit_feedback': booking.can_submit_feedback(),
    }
    return render(request, 'mainapp/booking_detail.html', context)

@login_required
@require_http_methods(["POST"])
def submit_feedback(request, booking_id):
    try:
        booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
        
        # Debug logging
        logger.info(f"Attempting to submit feedback for booking {booking_id}")
        logger.info(f"Booking status: {booking.status}")
        logger.info(f"Can submit feedback: {booking.can_submit_feedback()}")
        
        if not booking.can_submit_feedback():
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot submit feedback for this booking'
            })
        
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        # Debug logging
        logger.info(f"Received rating: {rating}")
        logger.info(f"Received comment: {comment}")
        
        if not rating or not comment:
            return JsonResponse({
                'status': 'error',
                'message': 'Both rating and comment are required'
            })
        
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Rating must be between 1 and 5'
                })
            
            feedback = Feedback.objects.create(
                booking=booking,
                rating=rating,
                comment=comment
            )
            
            # Debug logging
            logger.info(f"Feedback created successfully: {feedback.id}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Thank you for your feedback!'
            })
            
        except ValueError as ve:
            logger.error(f"ValueError in submit_feedback: {str(ve)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid rating value'
            })
            
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        logger.error(traceback.format_exc())  # Add full traceback
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        })

@csrf_exempt
def chatbot_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # Get user info if logged in
            user_context = ""
            greeting = "Hello! Welcome to WheelsOnRent."
            
            if request.user.is_authenticated:
                user = request.user
                # Get user's name
                user_name = user.get_full_name() or user.username
                greeting = f"Hello {user_name}! Welcome back to WheelsOnRent."
                
                # Get user's current bookings
                current_bookings = Booking.objects.filter(
                    user=user, 
                    status__in=['pending', 'confirmed']
                ).order_by('-start_date')
                
                if current_bookings.exists():
                    latest_booking = current_bookings[0]
                    user_context = f"""
                    Customer Name: {user_name}
                    Current Booking:
                    - Vehicle: {latest_booking.vehicle.model}
                    - Start Date: {latest_booking.start_date}
                    - End Date: {latest_booking.end_date}
                    - Status: {latest_booking.status}
                    """
                else:
                    user_context = f"Customer Name: {user_name}\nNo current bookings."

            # Get available vehicles and format them nicely
            available_vehicles = Vehicle.objects.filter(status=1)
            vehicle_info = "\n".join([
                f"🚗 {v.model} ({v.year})\n"
                f"   💰 Daily Rate: ₹{v.rental_rate:,}\n"
                f"   ✨ Features: {v.features}\n"
                "   ──────────────"
                for v in available_vehicles
            ])

            try:
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a helpful assistant for WheelsOnRent, a car rental website.
                            
                            {user_context}
                            
                            Our Premium Vehicle Collection:
                            {vehicle_info}
                            
                            Help customers with:
                            - Finding suitable vehicles from the list above
                            - Providing accurate pricing information
                            - Explaining booking process
                            - Answering questions about rental policies
                            
                            Always address the customer by name if available.
                            Keep responses friendly and concise."""
                        },
                        {
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                    model="gpt-4o",
                    temperature=0.7,
                    max_tokens=4096,
                    top_p=1
                )

                # Get AI response and add greeting for first-time messages
                ai_response = response.choices[0].message.content
                if request.user.is_authenticated:
                    ai_response = f"{greeting}\n\n{ai_response}"

                return JsonResponse({
                    'status': 'success',
                    'message': ai_response
                })

            except Exception as e:
                logger.error(f"AI model error: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Error getting response from AI model'
                }, status=500)

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred'
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)

@csrf_exempt
def chatbot_response(request):
    if request.method == 'POST':
        message = request.POST.get('message', '')
        
        # Get personalized responses if user is logged in
        if request.user.is_authenticated:
            user = request.user
            responses = {
                'hi': f'Hello {user.get_full_name() or user.username}! How can I help you today?',
                'hello': f'Hi {user.get_full_name() or user.username}! How can I assist you?',
                'my bookings': 'Let me check your bookings...',
                'booking': 'To make a booking, please browse our vehicles and click the "Book Now" button on your preferred vehicle.',
                'cancel': 'You can cancel your booking from your booking history page, at least 24 hours before the start time.',
                'payment': 'We accept all major credit cards and provide secure payment processing.',
                'contact': 'You can reach our support team at support@wheelsonrent.com',
                'price': 'Our prices vary depending on the vehicle. Please check individual vehicle listings for exact rates.',
                'location': 'We operate in multiple locations. You can find specific location details on each vehicle listing.',
            }
            
            if message.lower().strip() == 'my bookings':
                current_bookings = Booking.objects.filter(user=user, status__in=['pending', 'confirmed']).order_by('-start_date')
                if current_bookings.exists():
                    booking = current_bookings[0]
                    return JsonResponse({'reply': f'Your current booking is for a {booking.vehicle.model}, from {booking.start_date} to {booking.end_date}. Status: {booking.status}'})
                else:
                    return JsonResponse({'reply': 'You have no current bookings.'})
        else:
            responses = {
                'hi': 'Hello! How can I help you today?',
                'hello': 'Hi there! How can I assist you?',
                'booking': 'To make a booking, please browse our vehicles and click the "Book Now" button on your preferred vehicle.',
                'cancel': 'You can cancel your booking from your booking history page, at least 24 hours before the start time.',
                'payment': 'We accept all major credit cards and provide secure payment processing.',
                'contact': 'You can reach our support team at support@wheelsonrent.com',
                'price': 'Our prices vary depending on the vehicle. Please check individual vehicle listings for exact rates.',
                'location': 'We operate in multiple locations. You can find specific location details on each vehicle listing.',
            }

        # Default response if no keyword matches
        reply = responses.get(message.lower().strip(), 
            "I'm here to help with bookings, cancellations, payments, and general inquiries. "
            "Could you please be more specific about what you'd like to know?")

        return JsonResponse({'reply': reply})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def current_rentals(request):
    """View for displaying user's current rentals"""
    active_bookings = Booking.objects.filter(
        user=request.user,
        status__in=['picked_up']
    ).select_related('vehicle', 'vehicle__vendor')
    
    context = {
        'active_bookings': active_bookings
    }
    
    return render(request, 'mainapp/current_rentals.html', context)

@login_required
def rental_details(request, booking_id):
    """View for displaying details of a specific rental"""
    booking = get_object_or_404(
        Booking, 
        booking_id=booking_id, 
        user=request.user, 
        status__in=['confirmed', 'picked_up']
    )
    
    # Get any accident reports
    accident_reports = AccidentReport.objects.filter(booking=booking)
    
    # Check if extension is possible
    extension_possible = False
    if booking.status == 'picked_up':
        # Check if there's a 7-day window available for extension
        potential_end_date = booking.end_date + timezone.timedelta(days=7)
        extension_possible = booking.check_extension_availability(potential_end_date)
    
    context = {
        'booking': booking,
        'vehicle': booking.vehicle,
        'vendor': booking.vehicle.vendor,
        'accident_reports': accident_reports,
        'extension_possible': extension_possible
    }
    
    return render(request, 'mainapp/rental_details.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def early_return(request, booking_id):
    """Process early return of a vehicle with OTP verification and refund calculation"""
    booking = get_object_or_404(
        Booking, 
        booking_id=booking_id, 
        user=request.user, 
        status='picked_up'
    )
    
    # If GET request, generate OTP for early return verification
    if request.method == "GET":
        # Generate a random 6-digit OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Save OTP in session with expiration time (10 minutes)
        request.session['early_return_otp'] = otp
        request.session['early_return_otp_expires'] = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()
        
        # Send OTP to user's email
        subject = 'OTP for Early Vehicle Return'
        message = f'Your OTP for early vehicle return is: {otp}. This OTP will expire in 10 minutes.'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [request.user.email]
        
        try:
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)
            return JsonResponse({'success': True, 'message': 'OTP sent to your email'})
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return JsonResponse({'success': False, 'message': 'Failed to send OTP'}, status=500)
    
    # If POST request, verify OTP and process early return
    elif request.method == "POST":
        submitted_otp = request.POST.get('otp')
        stored_otp = request.session.get('early_return_otp')
        otp_expires = request.session.get('early_return_otp_expires')
        
        # Validate OTP
        if not stored_otp or not otp_expires:
            messages.error(request, 'No OTP found. Please request a new OTP.')
            return redirect('mainapp:rental_details', booking_id=booking_id)
        
        if timezone.now() > timezone.datetime.fromisoformat(otp_expires):
            messages.error(request, 'OTP has expired. Please request a new OTP.')
            return redirect('mainapp:rental_details', booking_id=booking_id)
        
        if submitted_otp != stored_otp:
            messages.error(request, 'Invalid OTP. Please try again.')
            return redirect('mainapp:rental_details', booking_id=booking_id)
        
        # Clear OTP from session
        if 'early_return_otp' in request.session:
            del request.session['early_return_otp']
        if 'early_return_otp_expires' in request.session:
            del request.session['early_return_otp_expires']
        
        # Process early return
        success, unused_days = booking.process_early_return()
        
        if success:
            # If there are unused days, calculate refund amount with early return fee
            refund_amount = 0
            early_return_fee = 0
            
            if unused_days > 0:
                daily_rate = booking.vehicle.rental_rate
                total_unused_amount = daily_rate * unused_days
                
                # Apply early return fee (15% of the unused amount)
                # Convert 0.15 to Decimal to avoid type error
                early_return_fee = round(total_unused_amount * Decimal('0.15'), 2)
                refund_amount = total_unused_amount - early_return_fee
            
            # Mark vehicle as returned
            booking.vehicle.mark_as_returned()
            
            # Send return confirmation email
            booking.send_return_email()
            
            messages.success(request, f'Vehicle returned successfully. {unused_days} unused days.')
            
            # If refund applicable, show additional message
            if refund_amount > 0:
                messages.info(
                    request, 
                    f'A refund of ₹{refund_amount} will be processed (₹{early_return_fee} early return fee has been deducted). Refund will be credited within 5-7 business days.'
                )
            
            return redirect('mainapp:user_booking_history')
        else:
            messages.error(request, 'Unable to process early return. Please contact customer support.')
            return redirect('mainapp:rental_details', booking_id=booking_id)

@login_required
@require_http_methods(["GET", "POST"])
def report_accident(request, booking_id):
    """Report an accident for a current rental"""
    booking = get_object_or_404(
        Booking, 
        booking_id=booking_id, 
        user=request.user, 
        status='picked_up'
    )
    
    # Debug logging for API key
    logger.debug(f"Google Maps API Key in report_accident view: {settings.GOOGLE_MAPS_API_KEY[:5]}...")
    
    if request.method == 'POST':
        location = request.POST.get('location')
        description = request.POST.get('description')
        severity = request.POST.get('severity')
        
        # Handle latitude and longitude conversion - use the updated input field IDs
        try:
            latitude = float(request.POST.get('latitude-input') or request.POST.get('latitude', '0'))
            if latitude == 0:  # Default value if not provided
                latitude = None
        except (ValueError, TypeError):
            latitude = None
            
        try:
            longitude = float(request.POST.get('longitude-input') or request.POST.get('longitude', '0'))
            if longitude == 0:  # Default value if not provided
                longitude = None
        except (ValueError, TypeError):
            longitude = None
            
        is_emergency = request.POST.get('is_emergency') == 'on'
        photos = request.FILES.get('photos')
        
        # Log received values for debugging
        logger.debug(f"Accident report values - Location: {location}, Lat: {latitude}, Long: {longitude}")
        
        # Validate the required fields
        if not location or not description or not severity:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'mainapp/report_accident.html', {
                'booking': booking,
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
            })
        
        # Validate coordinates
        if latitude is None or longitude is None:
            messages.error(request, 'Please mark the accident location on the map.')
            return render(request, 'mainapp/report_accident.html', {
                'booking': booking,
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
            })
        
        accident_report = AccidentReport.objects.create(
            booking=booking,
            location=location,
            description=description,
            severity=severity,
            latitude=latitude,
            longitude=longitude,
            is_emergency=is_emergency,
            photos=photos
        )
        
        # Send notification to vendor
        send_accident_notification(accident_report)
        
        if is_emergency:
            # Send emergency notification
            messages.warning(request, 'Emergency services have been notified. Please stay at your location.')
        
        messages.success(request, 'Accident report submitted successfully.')
        return redirect('mainapp:rental_details', booking_id=booking_id)
    
    context = {
        'booking': booking,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
    }
    
    return render(request, 'mainapp/report_accident.html', context)

def send_accident_notification(accident_report):
    """Send notification to vendor about accident"""
    booking = accident_report.booking
    vendor_email = booking.vehicle.vendor.user.email
    
    subject = f'URGENT: Accident Report for Booking #{booking.booking_id}'
    html_message = render_to_string('emails/accident_notification.html', {
        'accident': accident_report,
        'booking': booking,
        'customer': booking.user,
        'vehicle': booking.vehicle
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [vendor_email],
        html_message=html_message,
        fail_silently=False
    )

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def share_location(request, booking_id):
    """Share location with vendor"""
    try:
        logger.info(f"Location share called for booking {booking_id}")
        logger.info(f"Request method: {request.method}")
        
        # Check if JSON data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                client_timestamp = data.get('timestamp')  # Get client timestamp if provided
                is_live_tracking = data.get('is_live_tracking', False)  # Get live tracking status
                accuracy = data.get('accuracy', None)  # Get location accuracy in meters if provided
            except json.JSONDecodeError:
                logger.error("Invalid JSON payload")
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        else:
            # Handle form data
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            client_timestamp = request.POST.get('timestamp')  # Get client timestamp if provided
            is_live_tracking = request.POST.get('is_live_tracking', False)  # Get live tracking status
            accuracy = request.POST.get('accuracy', None)  # Get location accuracy if provided
            
            # Convert string 'false'/'true' to boolean
            if isinstance(is_live_tracking, str):
                is_live_tracking = is_live_tracking.lower() == 'true'
                
            # Convert accuracy to float if present
            if accuracy and isinstance(accuracy, str):
                try:
                    accuracy = float(accuracy)
                except ValueError:
                    accuracy = None
        
        logger.info(f"Received coordinates: lat={latitude}, lng={longitude}, timestamp={client_timestamp}, live_tracking={is_live_tracking}, accuracy={accuracy}m")
        
        try:
            # Convert to float
            latitude = float(latitude)
            longitude = float(longitude)
            
            # Basic validation
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                raise ValueError("Coordinates out of valid range")
                
            logger.info(f"Valid coordinates: lat={latitude}, lng={longitude}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid coordinates: {str(e)}")
            messages.error(request, "Invalid location data. Please try again.")
            return redirect('mainapp:rental_details', booking_id=booking_id)
        
        # Allow both confirmed and picked_up status bookings
        booking = get_object_or_404(
            Booking, 
            booking_id=booking_id, 
            user=request.user, 
            status__in=['confirmed', 'picked_up']
        )
        
        logger.info(f"Booking found: {booking}, status: {booking.status}")
        
        # Create location share record
        location_data = {
            "booking": booking,
            "latitude": latitude,
            "longitude": longitude,
            "is_live_tracking": bool(is_live_tracking)  # Ensure boolean type
        }
        
        # Add accuracy if provided
        if accuracy is not None:
            location_data["accuracy"] = accuracy
        
        # If client timestamp is provided, parse and use it
        if client_timestamp:
            try:
                # Try to parse the client timestamp (accepts various formats)
                from dateutil import parser
                parsed_timestamp = parser.parse(client_timestamp)
                location_data["timestamp"] = parsed_timestamp
                logger.info(f"Using client timestamp: {parsed_timestamp}")
            except Exception as e:
                logger.warning(f"Could not parse client timestamp: {str(e)}")
                # Fall back to server time (default behavior)
        
        location_share = LocationShare.objects.create(**location_data)
        
        logger.info(f"Location share created: {location_share.id} with timestamp: {location_share.timestamp}, live_tracking: {location_share.is_live_tracking}, accuracy: {getattr(location_share, 'accuracy', 'N/A')}m")
        
        # If this is called from AJAX/fetch, return JSON
        if request.content_type == 'application/json':
            return JsonResponse({
                'status': 'success', 
                'message': 'Location shared successfully',
                'latitude': latitude,
                'longitude': longitude
            })
        
        # Otherwise return HTML response for form submissions - ADD LAT/LNG TO REDIRECT URL
        messages.success(request, "Location shared successfully with vendor")
        redirect_url = reverse('mainapp:rental_details', kwargs={'booking_id': booking_id})
        redirect_url = f"{redirect_url}?lat={latitude}&lng={longitude}"
        return redirect(redirect_url)
    
    except Exception as e:
        logger.error(f"Error sharing location: {str(e)}")
        logger.error(traceback.format_exc())
        
        # If this is called from AJAX/fetch, return JSON error
        if request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
        # Otherwise return HTML error
        messages.error(request, f"Error sharing location: {str(e)}")
        return redirect('mainapp:rental_details', booking_id=booking_id)

@login_required
@require_http_methods(["GET", "POST"])
def check_extension(request, booking_id):
    """Check availability and calculate price for booking extension"""
    booking = get_object_or_404(
        Booking, 
        booking_id=booking_id, 
        user=request.user, 
        status='picked_up'
    )
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.POST
            days = int(data.get('days', 0))
            
            if days <= 0:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Please select a valid number of days'
                })
            
            # Calculate new end date
            new_end_date = booking.end_date + timezone.timedelta(days=days)
            
            # Check availability
            is_available = booking.check_extension_availability(new_end_date)
            
            if not is_available:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Extension not available for the selected dates'
                })
            
            # Calculate extension amount
            extension_amount = booking.calculate_extension_amount(new_end_date)
            
            return JsonResponse({
                'status': 'success',
                'is_available': is_available,
                'extension_amount': float(extension_amount),
                'new_end_date': new_end_date.strftime('%Y-%m-%d'),
                'days': days
            })
            
        except Exception as e:
            logger.error(f"Error checking extension: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    # For GET requests, just render the form
    context = {
        'booking': booking
    }
    
    return render(request, 'mainapp/check_extension.html', context)

@login_required
@require_http_methods(["POST"])
def process_extension(request, booking_id):
    """Process booking extension and payment"""
    booking = get_object_or_404(
        Booking, 
        booking_id=booking_id, 
        user=request.user, 
        status='picked_up'
    )
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        days = int(data.get('days', 0))
        
        if days <= 0:
            return JsonResponse({
                'status': 'error', 
                'message': 'Please select a valid number of days'
            })
        
        # Calculate new end date
        new_end_date = booking.end_date + timezone.timedelta(days=days)
        
        # Check availability
        is_available = booking.check_extension_availability(new_end_date)
        
        if not is_available:
            return JsonResponse({
                'status': 'error', 
                'message': 'Extension not available for the selected dates'
            })
        
        # Calculate extension amount
        extension_amount = booking.calculate_extension_amount(new_end_date)
        
        # Create Stripe checkout session for extension payment
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'unit_amount': int(extension_amount * 100),
                    'product_data': {
                        'name': f'Booking Extension for {booking.booking_id}',
                        'description': f'Extend rental by {days} days',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.build_absolute_uri(reverse('mainapp:extension_success')) + 
                        f'?session_id={{CHECKOUT_SESSION_ID}}&booking_id={booking_id}&days={days}',
            cancel_url=request.build_absolute_uri(reverse('mainapp:rental_details', args=[booking_id])),
            client_reference_id=str(booking_id),
        )
        
        return JsonResponse({
            'status': 'success',
            'session_id': session.id,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY
        })
        
    except Exception as e:
        logger.error(f"Error processing extension: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def extension_success(request):
    """Handle successful extension payment"""
    session_id = request.GET.get('session_id')
    booking_id = request.GET.get('booking_id')
    days = int(request.GET.get('days', 0))
    
    if not session_id or not booking_id or days <= 0:
        messages.error(request, "Invalid extension confirmation")
        return redirect('mainapp:current_rentals')
    
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == "paid" and str(session.client_reference_id) == str(booking_id):
            # Calculate new end date
            new_end_date = booking.end_date + timezone.timedelta(days=days)
            
            # Process the extension
            success = booking.extend_booking(new_end_date, session.payment_intent)
            
            if success:
                # Send confirmation email
                send_extension_confirmation_email(booking, days)
                
                messages.success(request, f"Booking successfully extended by {days} days. New return date: {new_end_date.strftime('%Y-%m-%d')}")
            else:
                messages.error(request, "Booking extension failed. Please contact support.")
        else:
            messages.warning(request, "Payment was successful, but booking extension failed. Please contact support.")
        
    except stripe.error.StripeError as e:
        messages.error(request, f"An error occurred while processing your extension: {str(e)}")
    
    return redirect('mainapp:rental_details', booking_id=booking_id)

def send_extension_confirmation_email(booking, days):
    """Send confirmation email for booking extension"""
    subject = 'Booking Extension Confirmation'
    html_message = render_to_string('emails/extension_confirmation.html', {
        'booking': booking,
        'user': booking.user,
        'days': days,
        'new_end_date': booking.end_date,
    })
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = booking.user.email

    try:
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Extension confirmation email sent for booking {booking.booking_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send extension confirmation email for booking {booking.booking_id}: {str(e)}")
        return False

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def share_location_test(request, booking_id):
    """A simplified version of share_location that just returns success"""
    try:
        logger.info(f"Simple location share test called for booking {booking_id}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"POST data: {request.POST}")
        
        latitude = request.POST.get('latitude', '12.9716')
        longitude = request.POST.get('longitude', '77.5946')
        
        booking = get_object_or_404(
            Booking, 
            booking_id=booking_id, 
            user=request.user
        )
        
        # Create test location share
        LocationShare.objects.create(
            booking=booking,
            latitude=float(latitude),
            longitude=float(longitude)
        )
        
        messages.success(request, "Test location shared successfully")
        # Add coordinates to the redirect URL for map display
        redirect_url = reverse('mainapp:rental_details', kwargs={'booking_id': booking_id})
        redirect_url = f"{redirect_url}?lat={latitude}&lng={longitude}"
        return redirect(redirect_url)
    
    except Exception as e:
        logger.error(f"Error in test location sharing: {str(e)}")
        logger.error(traceback.format_exc())
        messages.error(request, f"Error in test: {str(e)}")
        return redirect('mainapp:rental_details', booking_id=booking_id)
