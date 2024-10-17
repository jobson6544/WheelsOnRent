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
from .forms import UserRegistrationForm, UserProfileForm, UserEditForm, UserProfileEditForm
from .models import UserProfile, Booking, User  # Import User directly from your models
from vendor.models import Vehicle
from datetime import datetime, timedelta
import logging
import stripe
from .utils import generate_verification_token
from django.contrib.sites.shortcuts import get_current_site
import traceback

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

def index(request):
    return render(request, 'index.html')

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
    return render(request, 'register.html', {'form': form})

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
                    return redirect('complete_profile')
                return redirect('home')
            else:
                messages.error(request, "Please verify your email before logging in.")
        else:
            messages.error(request, "Invalid email or password.")
    return render(request, 'user_login.html')

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
            duration = (end_date.date() - start_date.date()).days  # Duration in days
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
                'redirect_url': reverse('payment') + f'?booking_id={booking.booking_id}'
            })
        
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while processing your booking. Please try again later.'
            })

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
    
    return redirect('user_booking_history')

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
                'currency': 'usd',
                'unit_amount': int(amount * 100),
                'product_data': {
                    'name': f'Booking {booking.booking_id}',
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.build_absolute_uri(reverse('payment_success')) + f'?session_id={{CHECKOUT_SESSION_ID}}&booking_id={booking_id}',
        cancel_url=request.build_absolute_uri(reverse('payment_cancelled')) + f'?booking_id={booking_id}',
        client_reference_id=str(booking_id),
    )
    
    booking.stripe_payment_intent_id = session.payment_intent
    booking.save()

    return render(request, 'payment.html', {
        'session_id': session.id,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'booking': booking,
    })

def calculate_booking_amount(booking):
    if not booking or not booking.start_date or not booking.end_date or not booking.vehicle:
        return 0  # Return 0 if any required data is missing
    
    # Calculate the number of days
    num_days = (booking.end_date - booking.start_date).days + 1
    
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
        return redirect('home')
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
    
    return render(request, 'payment_success.html', {'booking': booking})

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
    return render(request, 'payment_cancelled.html')

def payment_error(request):
    return render(request, 'payment_error.html')

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
        wheels_on_rent_fees = [price * 0.04 for price in total_prices]
        vendor_profits = [price - fee for price, fee in zip(total_prices, wheels_on_rent_fees)]
        
        return JsonResponse({
            'total_prices': total_prices,
            'wheels_on_rent_fees': wheels_on_rent_fees,
            'vendor_profits': vendor_profits
        })
    
    return render(request, 'vendor_benefits.html', context)
