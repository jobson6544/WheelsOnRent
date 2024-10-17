import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Vehicle, VehicleCompany, Model, Registration, Image, Features, VehicleDocument, Vendor, Insurance, Pickup, Return
from .forms import VehicleForm, VendorUserForm, VendorProfileForm, VehicleCompanyForm, VehicleDocumentForm
from django.apps import apps
from django.views.decorators.cache import never_cache
from .decorators import vendor_required, vendor_status_check
from django.views.generic import ListView
from decimal import Decimal
from django.conf import settings  # Add this import
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from mainapp.models import Booking, User  # Adjust this import based on your project structure
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
import random
from django.core.mail import send_mail
import json
import joblib
import numpy as np

Booking = apps.get_model('mainapp', 'Booking')

logger = logging.getLogger(__name__)

@never_cache
def vendor_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None and user.role == 'vendor':
            try:
                vendor = Vendor.objects.get(user=user)
                if vendor.status == 'pending':
                    messages.info(request, "Your application is under review.")
                    return redirect('vendor:application_under_review')
                elif vendor.status == 'approved':
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')  # Specify the backend
                    messages.success(request, "Login successful.")
                    return redirect('vendor:dashboard')
                elif vendor.status == 'rejected':
                    messages.error(request, "Your application has been rejected.")
                    return redirect('vendor:application_rejected')
            except Vendor.DoesNotExist:
                messages.error(request, "Vendor profile not found.")
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, 'vendor/vendor_login.html')

@never_cache
def vendor_register_user(request):
    if request.method == 'POST':
        user_form = VendorUserForm(request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.role = 'vendor'
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'User registration successful. Please complete your vendor profile.')
            return redirect('vendor:register_profile')
    else:
        user_form = VendorUserForm()
    return render(request, 'vendor/vendor_register_user.html', {'user_form': user_form})

@never_cache
@login_required
def vendor_register_profile(request):
    if request.method == 'POST':
        vendor_form = VendorProfileForm(request.POST)
        if vendor_form.is_valid():
            vendor = vendor_form.save(commit=False)
            vendor.user = request.user
            vendor.status = 'pending'
            vendor.latitude = request.POST.get('latitude')
            vendor.longitude = request.POST.get('longitude')
            vendor.save()
            messages.success(request, 'Vendor registration completed successfully. Your application is under review.')
            return redirect('vendor:application_under_review')
    else:
        vendor_form = VendorProfileForm()
    
    context = {
        'vendor_form': vendor_form,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
    }
    return render(request, 'vendor/vendor_register_profile.html', context)

@never_cache
@vendor_status_check
def vendor_dashboard(request):
    try:
        vendor = Vendor.objects.get(user=request.user)
        vehicles = Vehicle.objects.filter(vendor=vendor)
        
        # Count total bookings for this vendor
        total_bookings = Booking.objects.filter(vehicle__in=vehicles).count()
        
        # Count total unique customers
        total_customers = Booking.objects.filter(vehicle__in=vehicles).values('user').distinct().count()
        
        # Fetch recent bookings
        recent_bookings = Booking.objects.filter(vehicle__in=vehicles).select_related('user', 'vehicle').order_by('-start_date')[:10]
        
        # Calculate the sum of active bookings
        active_bookings_sum = Booking.objects.filter(
            vehicle__in=vehicles,
            status='confirmed',
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        ).aggregate(total=Sum('vehicle__rental_rate'))['total'] or 0

    except Vendor.DoesNotExist:
        vendor = None
        vehicles = []
        total_bookings = 0
        total_customers = 0
        recent_bookings = []
        active_bookings_sum = 0

    context = {
        'vendor': vendor,
        'vehicles': vehicles,
        'total_bookings': total_bookings,
        'total_customers': total_customers,
        'bookings': recent_bookings,
        'active_bookings_sum': active_bookings_sum,
    }
    return render(request, 'vendor/dashboard.html', context)

@never_cache
@vendor_required 
@login_required
def add_vehicle(request):
    logger.debug("Entering add_vehicle view")
    if request.method == 'POST':
        logger.debug("POST request received")
        vehicle_form = VehicleForm(request.POST, request.FILES, vendor=request.user.vendor)
        document_form = VehicleDocumentForm(request.POST, request.FILES)
        
        logger.debug(f"POST data: {request.POST}")
        logger.debug(f"FILES data: {request.FILES}")
        
        if vehicle_form.is_valid() and document_form.is_valid():
            logger.debug("Both forms are valid")
            try:
                with transaction.atomic():
                    # Save Vehicle
                    vehicle = vehicle_form.save(commit=False)
                    vehicle.vendor = request.user.vendor  # Set the vendor to the logged-in user
                    vehicle.save()
                    logger.info(f"Vehicle saved to database: {vehicle.id}")
                    vehicle_form.save_m2m()  # Save many-to-many relationships
                    logger.debug("Many-to-many relationships saved")
                    
                    # Save Registration
                    registration = Registration.objects.create(
                        registration_number=vehicle_form.cleaned_data['registration_number'],
                        registration_date=vehicle_form.cleaned_data['registration_date'],
                        registration_end_date=vehicle_form.cleaned_data['registration_end_date']
                    )
                    logger.debug(f"Registration created: {registration.__dict__}")
                    vehicle.registration = registration
                    vehicle.save()
                    
                    # Save Insurance
                    insurance = Insurance.objects.create(
                        vehicle=vehicle,
                        policy_number=vehicle_form.cleaned_data['policy_number'],
                        policy_provider=vehicle_form.cleaned_data['policy_provider'],
                        coverage_type=vehicle_form.cleaned_data['coverage_type'],
                        start_date=vehicle_form.cleaned_data['insurance_start_date'],
                        end_date=vehicle_form.cleaned_data['insurance_end_date'],
                        road_tax_details=vehicle_form.cleaned_data['road_tax_details'],
                        fitness_expiry_date=vehicle_form.cleaned_data['fitness_expiry_date'],
                        puc_expiry_date=vehicle_form.cleaned_data['puc_expiry_date']
                    )
                    logger.info(f"Insurance saved: {insurance.id}")
                    
                    # Update Vehicle with Insurance
                    vehicle.insurance = insurance
                    vehicle.save()
                    logger.info(f"Vehicle updated with insurance: {vehicle.id}")
                    
                    # Save Documents
                    document = document_form.save(commit=False)
                    document.vehicle = vehicle
                    document.save()
                    logger.info(f"Document saved: {document.id}")
                    
                    # Predict price
                    predicted_price = vehicle.predict_price()
                    
                    # You can choose to set this as the initial rental rate or just display it
                    vehicle.rental_rate = predicted_price
                    vehicle.save()

                    messages.success(request, f'Vehicle added successfully! Suggested rental rate: ${predicted_price:.2f} per day.')
                    logger.info("Vehicle addition process completed successfully")
                    return redirect('vendor:vendor_vehicles')
            except Exception as e:
                logger.error(f"Error saving vehicle: {str(e)}", exc_info=True)
                messages.error(request, f"An error occurred while saving the vehicle: {str(e)}")
                # Rollback the vehicle save if any error occurs
                if 'vehicle' in locals():
                    vehicle.delete()
        else:
            logger.error(f"Form errors: {vehicle_form.errors}, {document_form.errors}")
            messages.error(request, 'Please correct the errors in the form.')
    else:
        logger.debug("GET request received, initializing forms")
        vehicle_form = VehicleForm(vendor=request.user.vendor)
        document_form = VehicleDocumentForm()
    
    context = {
        'vehicle_form': vehicle_form,
        'document_form': document_form,
        'today_date': timezone.now().date(),
    }
    logger.debug("Rendering add_vehicle template")
    return render(request, 'vendor/add_vehicle.html', context)

@never_cache
@vendor_required
def vendor_vehicles(request):
    vehicles = Vehicle.objects.filter(vendor__user=request.user, status=1).select_related(
        'model__sub_category__category', 'registration'
    ).prefetch_related('features')
    for vehicle in vehicles:
        print(f"Vehicle ID: {vehicle.id}")  # Add this line for debugging
    return render(request, 'vendor/vehicle_list.html', {'vehicles': vehicles})

@never_cache
@vendor_required
def update_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            try:
                with transaction.atomic():
                    vehicle = form.save(commit=False)
                    
                    # Update registration
                    vehicle.registration.registration_number = form.cleaned_data['registration_number']
                    vehicle.registration.registration_date = form.cleaned_data['registration_date']
                    vehicle.registration.registration_end_date = form.cleaned_data['registration_end_date']
                    vehicle.registration.save()

                    vehicle.save()
                    form.save_m2m()  # Save many-to-many relationships

                    if 'image' in request.FILES:
                        # Delete old image if exists
                        if vehicle.image:
                            vehicle.image.delete()
                        vehicle.image = request.FILES['image']
                        vehicle.save()

                messages.success(request, 'Vehicle updated successfully.')
                return redirect('vendor:vendor_vehicles')
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
    else:
        initial_data = {
            'vehicle_type': vehicle.model.sub_category.category.category_id,
            'vehicle_company': vehicle.model.sub_category.sub_category_id,
            'registration_number': vehicle.registration.registration_number,
            'registration_date': vehicle.registration.registration_date,
            'registration_end_date': vehicle.registration.registration_end_date,
        }
        form = VehicleForm(instance=vehicle, initial=initial_data)
    
    return render(request, 'vendor/update_vehicle.html', {'form': form, 'vehicle': vehicle})

@never_cache
@vendor_required
def delete_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    vehicle.status = 0
    vehicle.save()
    messages.success(request, 'Vehicle has been successfully deleted.')
    return redirect('vendor:vendor_vehicles')

@never_cache
@vendor_required
def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id, vendor__user=request.user, status=1)
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle has been successfully updated.')
            return redirect('vendor:vendor_vehicles')
    else:
        form = VehicleForm(instance=vehicle)
    return render(request, 'vendor/edit_vehicle.html', {'form': form, 'vehicle': vehicle})

@never_cache
@vendor_required
def vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    suggested_price = Decimal(str(vehicle.get_suggested_price()))  # Convert to Decimal

    if request.method == 'POST' and 'update_price' in request.POST:
        if vehicle.predicted_price:
            vehicle.rental_rate = vehicle.predicted_price
            vehicle.predicted_price = None  # Clear the temporary predicted price
            vehicle.save()
            messages.success(request, f'Rental rate updated to ${vehicle.rental_rate:.2f} per day.')
        else:
            messages.error(request, 'No predicted price available.')

    context = {
        'vehicle': vehicle,
        'suggested_price': suggested_price,
        'predicted_price': vehicle.predicted_price,
    }
    return render(request, 'vendor/vehicle_detail.html', context)

@never_cache
def application_under_review(request):
    return render(request, 'vendor/application_under_review.html')

@never_cache
def application_rejected(request):
    return render(request, 'vendor/application_rejected.html')

@never_cache
def get_companies(request, vehicle_type_id):
    companies = VehicleCompany.objects.filter(category_id=vehicle_type_id).values('sub_category_id', 'company_name')
    return JsonResponse(list(companies), safe=False)

@never_cache
def get_models(request, company_id):
    models = Model.objects.filter(sub_category_id=company_id).values('model_id', 'model_name')
    return JsonResponse(list(models), safe=False)

@never_cache
@vendor_required
def add_vehicle_company(request):
    if request.method == 'POST':
        form = VehicleCompanyForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('vehicle_company_list')  # Redirect to a list view
    else:
        form = VehicleCompanyForm()
    return render(request, 'vendor/add_vehicle_company.html', {'form': form})

class VehicleDashboardView(ListView):
    model = Vehicle
    template_name = 'vehicle_dashboard.html'
    context_object_name = 'vehicles'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for vehicle in context['vehicles']:
            vehicle.suggested_price = vehicle.get_suggested_price()
        return context

@login_required
def vendor_profile(request):
    vendor = request.user.vendor
    context = {
        'vendor': vendor,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
    }
    return render(request, 'vendor/vendor_profile.html', context)

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = VendorProfileForm(request.POST, request.FILES, instance=request.user.vendor)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.latitude = request.POST.get('latitude')
            vendor.longitude = request.POST.get('longitude')
            vendor.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('vendor:vendor_profile')
    else:
        form = VendorProfileForm(instance=request.user.vendor)
    
    context = {
        'form': form,
        'vendor': request.user.vendor,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY
    }
    return render(request, 'vendor/vendor_profile.html', context)

@never_cache
@never_cache
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
        vehicle_value = int(request.POST.get('vehicle_value', 0))
        
        # Calculate profits for all days up to rental_days
        profits = [round((day * vehicle_value) / 1000) for day in range(1, rental_days + 1)]
        
        return JsonResponse({'profits': profits})
    
    return render(request, 'vendor/vendor_benefits.html', context)

@login_required
@vendor_required
def vendor_bookings(request):
    vendor = request.user.vendor
    bookings = Booking.objects.filter(vehicle__vendor=vendor).order_by('-start_date')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(bookings, 10)  # Show 10 bookings per page

    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)

    context = {
        'bookings': bookings,
    }
    return render(request, 'vendor/vendor_bookings.html', context)


@login_required
@vendor_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, vehicle__vendor=request.user.vendor)
    context = {
        'booking': booking,
    }
    return render(request, 'vendor/booking_details.html', context)

@login_required
@vendor_required
def generate_pickup_qr(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, vehicle__vendor=request.user.vendor)
    pickup, created = Pickup.objects.get_or_create(booking=booking)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"{request.build_absolute_uri('/')[:-1]}{reverse('vendor:verify_pickup', args=[booking_id])}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code image
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    pickup.qr_code.save(f"pickup_qr_{booking_id}.png", ContentFile(buffer.getvalue()))
    
    # Send email with QR code
    subject = 'Vehicle Pickup QR Code'
    html_content = render_to_string('emails/pickup_qr.html', {'booking': booking})
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, 'from@example.com', [booking.user.email])
    email.attach_alternative(html_content, "text/html")
    email.attach(f'pickup_qr_{booking_id}.png', buffer.getvalue(), 'image/png')
    email.send()

    return JsonResponse({'success': True, 'message': 'QR code sent to customer email'})

@login_required
@vendor_required
def generate_return_qr(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, vehicle__vendor=request.user.vendor)
    return_obj, created = Return.objects.get_or_create(booking=booking)
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"{request.build_absolute_uri('/')[:-1]}{reverse('vendor:verify_return', args=[booking_id])}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code image
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return_obj.qr_code.save(f"return_qr_{booking_id}.png", ContentFile(buffer.getvalue()))
    
    # Send email with QR code
    subject = 'Vehicle Return QR Code'
    html_content = render_to_string('emails/return_qr.html', {'booking': booking})
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, 'from@example.com', [booking.user.email])
    email.attach_alternative(html_content, "text/html")
    email.attach(f'return_qr_{booking_id}.png', buffer.getvalue(), 'image/png')
    email.send()

    return JsonResponse({'success': True, 'message': 'QR code sent to customer email'})



@login_required
@vendor_required
def send_otp(request, booking_id):
    if request.method == 'POST':
        try:
            booking = get_object_or_404(Booking, booking_id=booking_id)
            pickup, created = Pickup.objects.get_or_create(booking=booking)
            
            # Generate new OTP
            new_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            pickup.otp = new_otp
            pickup.save()
            
            # Send OTP to customer's email
            subject = 'Your OTP for Vehicle Pickup'
            message = f'Your OTP for vehicle pickup is: {new_otp}'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [booking.user.email]
            
            logger.info(f"Attempting to send OTP email to {recipient_list}")
            
            try:
                send_mail(subject, message, from_email, recipient_list, fail_silently=False)
                logger.info(f"OTP email sent successfully to {recipient_list}")
                return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
            except Exception as e:
                logger.error(f"Failed to send OTP email: {str(e)}")
                return JsonResponse({'success': False, 'message': f'Failed to send OTP email: {str(e)}'}, status=500)
        
        except Exception as e:
            logger.error(f"Error in send_otp view: {str(e)}")
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

@login_required
@vendor_required
def verify_pickup(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, vehicle__vendor=request.user.vendor)
        pickup = get_object_or_404(Pickup, booking=booking)
        otp = request.POST.get('otp')
        
        if otp == pickup.otp:
            pickup.is_verified = True
            pickup.pickup_time = timezone.now()
            pickup.save()
            booking.vehicle.mark_as_delivered()
            booking.send_pickup_email()
            return JsonResponse({'success': True, 'message': 'Vehicle delivered successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'})

@login_required
@vendor_required
def verify_return(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, vehicle__vendor=request.user.vendor)
        return_obj = get_object_or_404(Return, booking=booking)
        otp = request.POST.get('otp')
        
        if otp == return_obj.otp:
            return_obj.is_verified = True
            return_obj.return_time = timezone.now()
            return_obj.save()
            booking.vehicle.mark_as_returned()
            booking.send_return_email()
            booking.send_feedback_email()
            return JsonResponse({'success': True, 'message': 'Vehicle returned successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'})

@login_required
@vendor_required
def scan_qr(request):
    return render(request, 'vendor/scan_qr.html')

@login_required
@vendor_required
def booking_details(request, booking_data):
    try:
        data = json.loads(booking_data)
        booking = get_object_or_404(Booking, booking_id=data['booking_id'])
        customer = get_object_or_404(User, id=data['customer_id'])
        
        context = {
            'booking': booking,
            'customer': customer,
            'qr_type': data['type'],
        }
        
        return render(request, 'vendor/booking_details.html', context)
    except json.JSONDecodeError:
        messages.error(request, "Invalid QR code data")
        return redirect('vendor:scan_qr')

@login_required
@vendor_required
def send_otp(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        qr_type = request.POST.get('qr_type')
        
        if qr_type == 'pickup':
            pickup, created = Pickup.objects.get_or_create(booking=booking)
            otp_object = pickup
        elif qr_type == 'return':
            return_obj, created = Return.objects.get_or_create(booking=booking)
            otp_object = return_obj
        else:
            return JsonResponse({'success': False, 'message': 'Invalid QR type'})
        
        # Generate new OTP
        new_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        otp_object.otp = new_otp
        otp_object.otp_created_at = timezone.now()
        otp_object.save()
        
        # Send OTP to customer's email
        subject = f'Your OTP for Vehicle {qr_type.capitalize()}'
        message = f'Your OTP for vehicle {qr_type} is: {new_otp}. This OTP will expire in 5 minutes.'
        booking.user.email_user(subject, message)
        
        # Store OTP in session
        request.session[f'{qr_type}_otp'] = new_otp
        request.session[f'{qr_type}_otp_expires'] = (timezone.now() + timezone.timedelta(minutes=5)).isoformat()
        
        return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@vendor_required
def verify_otp(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        qr_type = request.POST.get('qr_type')
        otp = request.POST.get('otp')
        
        stored_otp = request.session.get(f'{qr_type}_otp')
        otp_expires = request.session.get(f'{qr_type}_otp_expires')
        
        if not stored_otp or not otp_expires:
            return JsonResponse({'success': False, 'message': 'OTP has not been sent'})
        
        if timezone.now() > timezone.datetime.fromisoformat(otp_expires):
            return JsonResponse({'success': False, 'message': 'OTP has expired'})
        
        if otp == stored_otp:
            if qr_type == 'pickup':
                pickup, created = Pickup.objects.get_or_create(booking=booking)
                pickup.is_verified = True
                pickup.pickup_time = timezone.now()
                pickup.save()
                booking.status = 'picked_up'
                booking.vehicle.mark_as_rented()
                booking.send_pickup_email()
            elif qr_type == 'return':
                return_obj, created = Return.objects.get_or_create(booking=booking)
                return_obj.is_verified = True
                return_obj.return_time = timezone.now()
                return_obj.save()
                booking.status = 'returned'
                booking.vehicle.mark_as_returned()
                booking.send_return_email()
            
            booking.save()
            
            # Clear OTP from session
            del request.session[f'{qr_type}_otp']
            del request.session[f'{qr_type}_otp_expires']
            
            return JsonResponse({'success': True, 'message': f'Vehicle {qr_type} verified successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@never_cache
@vendor_required
def predict_price(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, vendor__user=request.user)
    predicted_price = vehicle.predict_price()
    vehicle.predicted_price = predicted_price  # Store the predicted price temporarily
    vehicle.save(update_fields=['predicted_price'])
    messages.success(request, f'Predicted rental rate for {vehicle.model}: ${predicted_price:.2f} per day.')
    return redirect('vendor:vehicle_detail', vehicle_id=vehicle.id)