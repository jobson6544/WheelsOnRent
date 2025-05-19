import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Max
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
from mainapp.models import Booking, User, AccidentReport, LocationShare
from mainapp.constants import PLATFORM_FEE_PERCENTAGE
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
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import HttpResponse
import csv
import xlsxwriter
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from datetime import datetime, timedelta
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Spacer, Paragraph
import os
import pandas as pd

Booking = apps.get_model('mainapp', 'Booking')
User = get_user_model()

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
        
        if vehicle_form.is_valid() and document_form.is_valid():
            logger.debug("Both forms are valid")
            try:
                with transaction.atomic():
                    # Save Vehicle
                    vehicle = vehicle_form.save(commit=False)
                    vehicle.vendor = request.user.vendor
                    
                    # Set initial rental rate if not provided
                    if not vehicle.rental_rate:
                        try:
                            predicted_price = vehicle.predict_price()
                            vehicle.rental_rate = predicted_price
                        except Exception as e:
                            logger.error(f"Price prediction failed: {str(e)}")
                            vehicle.rental_rate = 50.00  # Default price
                    
                    vehicle.save()
                    vehicle_form.save_m2m()
                    
                    # Save Registration
                    registration = Registration.objects.create(
                        registration_number=vehicle_form.cleaned_data['registration_number'],
                        registration_date=vehicle_form.cleaned_data['registration_date'],
                        registration_end_date=vehicle_form.cleaned_data['registration_end_date']
                    )
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
                    
                    messages.success(request, f'Vehicle added successfully! Initial rental rate set to ${vehicle.rental_rate:.2f} per day.')
                    return redirect('vendor:vendor_vehicles')
                    
            except Exception as e:
                logger.error(f"Error saving vehicle: {str(e)}", exc_info=True)
                messages.error(request, "An error occurred while saving the vehicle. Please try again.")
                if 'vehicle' in locals():
                    vehicle.delete()
        else:
            logger.error(f"Form errors: {vehicle_form.errors}, {document_form.errors}")
            messages.error(request, 'Please correct the errors in the form.')
    else:
        vehicle_form = VehicleForm(vendor=request.user.vendor)
        document_form = VehicleDocumentForm()
    
    context = {
        'vehicle_form': vehicle_form,
        'document_form': document_form,
        'today_date': timezone.now().date(),
    }
    return render(request, 'vendor/add_vehicle.html', context)

@never_cache
@vendor_required
def vendor_vehicles(request):
    try:
        # Get all vehicles for the current vendor
        vehicles = Vehicle.objects.filter(
            vendor=request.user.vendor
        ).select_related(
            'model',
            'model__sub_category',
            'model__sub_category__category',
            'registration',
            'insurance'
        ).prefetch_related('features')

        context = {
            'vehicles': vehicles,
            'has_vehicles': vehicles.exists(),
            'active_page': 'vehicles'
        }
        return render(request, 'vendor/vehicle_list.html', context)
    except Exception as e:
        logger.error(f"Error in vendor_vehicles view: {str(e)}")
        messages.error(request, "An error occurred while retrieving vehicles.")
        return redirect('vendor:dashboard')

@never_cache
@vendor_required
def update_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, vendor=request.user.vendor)
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle, vendor=request.user.vendor)
        if form.is_valid():
            try:
                with transaction.atomic():
                    vehicle = form.save(commit=False)
                    
                    # Update registration
                    vehicle.registration.registration_number = form.cleaned_data['registration_number']
                    vehicle.registration.registration_date = form.cleaned_data['registration_date']
                    vehicle.registration.registration_end_date = form.cleaned_data['registration_end_date']
                    vehicle.registration.save()

                    # Update insurance if it exists
                    if vehicle.insurance:
                        vehicle.insurance.policy_number = form.cleaned_data['policy_number']
                        vehicle.insurance.policy_provider = form.cleaned_data['policy_provider']
                        vehicle.insurance.coverage_type = form.cleaned_data['coverage_type']
                        vehicle.insurance.start_date = form.cleaned_data['insurance_start_date']
                        vehicle.insurance.end_date = form.cleaned_data['insurance_end_date']
                        vehicle.insurance.road_tax_details = form.cleaned_data['road_tax_details']
                        vehicle.insurance.fitness_expiry_date = form.cleaned_data['fitness_expiry_date']
                        vehicle.insurance.puc_expiry_date = form.cleaned_data['puc_expiry_date']
                        vehicle.insurance.save()

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
        # Comprehensive initial data
        initial_data = {
            'vehicle_type': vehicle.model.sub_category.category.category_id,
            'vehicle_company': vehicle.model.sub_category.sub_category_id,
            'registration_number': vehicle.registration.registration_number,
            'registration_date': vehicle.registration.registration_date,
            'registration_end_date': vehicle.registration.registration_end_date,
        }
        
        # Add insurance data if available
        if hasattr(vehicle, 'insurance') and vehicle.insurance:
            initial_data.update({
                'policy_number': vehicle.insurance.policy_number,
                'policy_provider': vehicle.insurance.policy_provider,
                'coverage_type': vehicle.insurance.coverage_type,
                'insurance_start_date': vehicle.insurance.start_date,
                'insurance_end_date': vehicle.insurance.end_date,
                'road_tax_details': vehicle.insurance.road_tax_details,
                'fitness_expiry_date': vehicle.insurance.fitness_expiry_date,
                'puc_expiry_date': vehicle.insurance.puc_expiry_date,
            })
            
        form = VehicleForm(instance=vehicle, initial=initial_data, vendor=request.user.vendor)
    
    return render(request, 'vendor/update_vehicle.html', {'form': form, 'vehicle': vehicle})

@never_cache
@vendor_required
def delete_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, vendor=request.user.vendor)
    vehicle.status = 'unavailable'  # Update to use the status choices from the model
    vehicle.availability = False
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
@login_required
def vendor_profile(request):
    vendor = request.user.vendor
    context = {
        'vendor': vendor,
        'profile_picture_url': vendor.get_profile_picture_url(),
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
            if 'profile_picture' in request.FILES:
                vendor.profile_picture = request.FILES['profile_picture']
            vendor.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('vendor:profile')  # Changed this line
    else:
        form = VendorProfileForm(instance=request.user.vendor)
    
    context = {
        'form': form,
        'vendor': request.user.vendor,
        'profile_picture_url': request.user.vendor.get_profile_picture_url(),
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
@login_required
def predict_price(request, vehicle_id):
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, vendor=request.user.vendor)
        
        try:
            # Prepare features for prediction
            features = pd.DataFrame({
                'year': [float(vehicle.year)],
                'mileage': [float(vehicle.mileage)],
                'seating_capacity': [float(vehicle.seating_capacity)],
                'air_conditioning': [1.0 if vehicle.air_conditioning else 0.0],
                'fuel_efficiency': [float(vehicle.fuel_efficiency)],
                'model_year': [float(vehicle.model.model_year)],
                'num_features': [float(vehicle.features.count())],
                'transmission_manual': [0.0 if vehicle.transmission == 'automatic' else 1.0],
                'fuel_type_diesel': [1.0 if vehicle.fuel_type == 'diesel' else 0.0],
                'fuel_type_electric': [1.0 if vehicle.fuel_type == 'electric' else 0.0],
                'fuel_type_hybrid': [1.0 if vehicle.fuel_type == 'hybrid' else 0.0],
                'fuel_type_lpg': [1.0 if vehicle.fuel_type == 'lpg' else 0.0],
                'fuel_type_petrol': [1.0 if vehicle.fuel_type == 'petrol' else 0.0],
                'vehicle_type_luxury': [1.0 if vehicle.model.sub_category.category.category_name.lower() == 'luxury' else 0.0],
                'vehicle_type_sedan': [1.0 if vehicle.model.sub_category.category.category_name.lower() == 'sedan' else 0.0],
                'vehicle_type_suv': [1.0 if vehicle.model.sub_category.category.category_name.lower() == 'suv' else 0.0],
                'vehicle_type_van': [1.0 if vehicle.model.sub_category.category.category_name.lower() == 'van' else 0.0],
                'brand_tier_luxury': [1.0 if vehicle.model.sub_category.company_name.lower() == 'luxury' else 0.0],
                'brand_tier_mid-range': [1.0 if vehicle.model.sub_category.company_name.lower() == 'mid-range' else 0.0],
                'brand_tier_premium': [1.0 if vehicle.model.sub_category.company_name.lower() == 'premium' else 0.0],
            })
        except AttributeError as e:
            logger.error(f"Attribute error while preparing features: {str(e)}")
            messages.error(request, f"Error preparing vehicle data: {str(e)}. Please ensure all vehicle details are complete.")
            return redirect('vendor:vendor_vehicles')

        try:
            # Load the model
            model_path = os.path.join(settings.BASE_DIR, 'trained_rental_price_model.joblib')
            model = joblib.load(model_path)
            
            # Make prediction
            predicted_price = model.predict(features)[0]
            
            # Add platform fee
            platform_fee_multiplier = 1 + (PLATFORM_FEE_PERCENTAGE / 100)
            final_price = round(float(predicted_price) * platform_fee_multiplier, 2)
            
            if request.method == 'POST' and 'update_price' in request.POST:
                vehicle.rental_rate = final_price
                vehicle.save()
                messages.success(request, 'Rental rate updated successfully!')
                return redirect('vendor:vehicle_detail', vehicle_id=vehicle.id)
            
            context = {
                'vehicle': vehicle,
                'predicted_price': final_price,
                'current_price': vehicle.rental_rate,
                'vehicle_types': [vehicle.model.sub_category.category]
            }
            
            return render(request, 'vendor/predict_price.html', context)
            
        except FileNotFoundError:
            logger.error(f"ML model file not found at path: {model_path}")
            messages.warning(request, "Using fallback price prediction method (model file not found).")
            # Fallback calculation
            base_price = float(vehicle.rental_rate) if vehicle.rental_rate else 50.0
            predicted_price = base_price * (1 + (vehicle.features.count() * 0.05))
            return render(request, 'vendor/predict_price.html', {
                'vehicle': vehicle,
                'predicted_price': round(predicted_price, 2),
                'current_price': vehicle.rental_rate,
                'vehicle_types': [vehicle.model.sub_category.category]
            })
        except KeyError as e:
            logger.error(f"KeyError in predict_price: {str(e)}. Feature mismatch between model and input data.")
            messages.error(request, f"Model feature mismatch: {str(e)}. Please retrain the model.")
            return redirect('vendor:vendor_vehicles')
        except Exception as e:
            logger.error(f"Error loading or using ML model: {str(e)}", exc_info=True)
            messages.error(request, f"Error with price prediction model: {str(e)}.")
            return redirect('vendor:vendor_vehicles')
            
    except Exception as e:
        logger.error(f"Error in predict_price view for vehicle {vehicle_id}: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while predicting the price: {str(e)}")
        return redirect('vendor:vendor_vehicles')

@require_http_methods(["GET", "POST"])
def vendor_forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, is_active=True, role='vendor')
            vendor = Vendor.objects.get(user=user, status='approved')
            token = vendor.generate_password_reset_token()
            reset_url = request.build_absolute_uri(reverse('vendor:vendor_password_reset_verify'))
            send_mail(
                'Password Reset OTP',
                f'Your OTP for password reset is: {token}\nUse this OTP at {reset_url}',
                'from@example.com',
                [user.email],
                fail_silently=False,
            )
            return JsonResponse({'status': 'success', 'message': 'A password reset OTP has been sent to your email.'})
        except (User.DoesNotExist, Vendor.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'No active vendor account found with this email address.'})
    return render(request, 'vendor/vendor_forgot_password.html')

@require_http_methods(["GET", "POST"])
def vendor_password_reset_verify(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        token = request.POST.get('token')
        new_password = request.POST.get('new_password')
        try:
            user = User.objects.get(email=email, is_active=True, role='vendor')
            vendor = Vendor.objects.get(user=user, status='approved')
            if vendor.password_reset_token == token and vendor.is_password_reset_token_valid():
                user.set_password(new_password)
                user.save()
                vendor.password_reset_token = None
                vendor.password_reset_token_created_at = None
                vendor.save()
                return JsonResponse({'status': 'success', 'message': 'Your password has been reset successfully. You can now login with your new password.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP. Please try again.'})
        except (User.DoesNotExist, Vendor.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'No active vendor account found with this email address.'})
    return render(request, 'vendor/vendor_password_reset_verify.html')

@login_required
@vendor_required
@login_required
@vendor_required
def view_feedback(request):
    vendor = get_object_or_404(Vendor, user=request.user)
    
    # Get filter parameters from request
    rating_filter = request.GET.get('rating')
    date_filter = request.GET.get('date')
    sort_by = request.GET.get('sort')
    
    # Start with all feedback for this vendor's vehicles
    feedbacks = Booking.objects.filter(
        vehicle__vendor=vendor,
        feedback__isnull=False
    ).select_related(
        'user',
        'vehicle',
        'feedback'
    )
    
    # Apply filters
    if rating_filter:
        feedbacks = feedbacks.filter(feedback__rating=rating_filter)
    
    if date_filter:
        if date_filter == 'last_week':
            feedbacks = feedbacks.filter(feedback__created_at__gte=timezone.now() - timezone.timedelta(days=7))
        elif date_filter == 'last_month':
            feedbacks = feedbacks.filter(feedback__created_at__gte=timezone.now() - timezone.timedelta(days=30))
        elif date_filter == 'last_year':
            feedbacks = feedbacks.filter(feedback__created_at__gte=timezone.now() - timezone.timedelta(days=365))
    
    # Apply sorting
    if sort_by == 'rating_high':
        feedbacks = feedbacks.order_by('-feedback__rating')
    elif sort_by == 'rating_low':
        feedbacks = feedbacks.order_by('feedback__rating')
    elif sort_by == 'date_new':
        feedbacks = feedbacks.order_by('-feedback__created_at')
    elif sort_by == 'date_old':
        feedbacks = feedbacks.order_by('feedback__created_at')
    else:
        feedbacks = feedbacks.order_by('-feedback__created_at')  # Default sort by newest
    
    # Calculate statistics
    total_feedback = feedbacks.count()
    avg_rating = feedbacks.aggregate(Avg('feedback__rating'))['feedback__rating__avg'] or 0
    rating_distribution = feedbacks.values('feedback__rating').annotate(
        count=Count('feedback__rating')
    ).order_by('feedback__rating')
    
    # Pagination
    paginator = Paginator(feedbacks, 10)  # Show 10 feedbacks per page
    page = request.GET.get('page')
    try:
        feedbacks_page = paginator.page(page)
    except PageNotAnInteger:
        feedbacks_page = paginator.page(1)
    except EmptyPage:
        feedbacks_page = paginator.page(paginator.num_pages)
    
    context = {
        'feedbacks': feedbacks_page,
        'total_feedback': total_feedback,
        'avg_rating': round(avg_rating, 1),
        'rating_distribution': rating_distribution,
        'current_rating_filter': rating_filter,
        'current_date_filter': date_filter,
        'current_sort': sort_by,
    }
    
    return render(request, 'vendor/feedback_list.html', context)


@login_required
@vendor_required
def customer_list(request):
    vendor = get_object_or_404(Vendor, user=request.user)
    
    # Get all unique customers who have booked this vendor's vehicles
    customers = User.objects.filter(
        booking__vehicle__vendor=vendor
    ).distinct().annotate(
        total_bookings=Count('booking'),
        total_spent=Sum('booking__total_amount'),
        last_booking=Max('booking__start_date'),  # Changed from created_at to start_date
        avg_rating=Avg('booking__feedback__rating')
    )
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort', 'last_booking')
    if sort_by == 'name':
        customers = customers.order_by('full_name')
    elif sort_by == 'bookings':
        customers = customers.order_by('-total_bookings')
    elif sort_by == 'spent':
        customers = customers.order_by('-total_spent')
    elif sort_by == 'rating':
        customers = customers.order_by('-avg_rating')
    else:  # default sort by last booking
        customers = customers.order_by('-last_booking')
    
    # Pagination
    paginator = Paginator(customers, 10)  # Show 10 customers per page
    page = request.GET.get('page')
    try:
        customers_page = paginator.page(page)
    except PageNotAnInteger:
        customers_page = paginator.page(1)
    except EmptyPage:
        customers_page = paginator.page(paginator.num_pages)
    
    context = {
        'customers': customers_page,
        'search_query': search_query,
        'current_sort': sort_by,
    }
    
    return render(request, 'vendor/customer_list.html', context)

@login_required
@vendor_required
def reports_dashboard(request):
    vendor = request.user.vendor
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=30)  # Last 30 days

    # Get bookings data
    bookings = Booking.objects.filter(
        vehicle__vendor=vendor,
        start_date__range=[start_date, end_date]
    ).order_by('start_date')

    # Calculate total revenue from completed bookings
    total_revenue = Booking.objects.filter(
        vehicle__vendor=vendor,
        status='returned'
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    # Calculate average feedback rating
    avg_rating = Booking.objects.filter(
        vehicle__vendor=vendor,
        status='returned',
        feedback__isnull=False
    ).aggregate(
        avg_rating=Avg('feedback__rating')
    )['avg_rating'] or 0

    # Prepare data for charts
    booking_dates = []
    booking_counts = []
    revenue_amounts = []

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        daily_bookings = bookings.filter(start_date__date=current_date.date()).count()
        daily_revenue = bookings.filter(
            start_date__date=current_date.date(),
            status='returned'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        booking_dates.append(date_str)
        booking_counts.append(daily_bookings)
        revenue_amounts.append(float(daily_revenue))

        current_date += timezone.timedelta(days=1)

    context = {
        'total_bookings': bookings.count(),
        'total_vehicles': Vehicle.objects.filter(vendor=vendor).count(),
        'total_revenue': total_revenue,
        'avg_rating': round(avg_rating, 1),  # Round to 1 decimal place
        'booking_dates': json.dumps(booking_dates),
        'booking_counts': json.dumps(booking_counts),
        'revenue_dates': json.dumps(booking_dates),
        'revenue_amounts': json.dumps(revenue_amounts),
    }

    return render(request, 'vendor/report_dashboard.html', context)

@login_required
@vendor_required
def generate_report(request):
    vendor = request.user.vendor
    report_type = request.GET.get('type')
    file_format = request.GET.get('format')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    try:
        # Convert string dates to datetime objects
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            start_date = start_date.replace(hour=0, minute=0, second=0)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            date_range_text = f"Period: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        else:
            date_range_text = "All Time"

        # Get data based on report type
        if report_type == 'booking':
            headers = ['Booking ID', 'Customer', 'Vehicle', 'Start Date', 'End Date', 'Status', 'Amount']
            bookings = Booking.objects.filter(vehicle__vendor=vendor)
            if start_date and end_date:
                bookings = bookings.filter(start_date__range=[start_date, end_date])
            
            table_data = [[
                booking.booking_id,
                booking.user.get_full_name(),
                str(booking.vehicle),
                booking.start_date.strftime('%Y-%m-%d'),
                booking.end_date.strftime('%Y-%m-%d'),
                booking.status,
                f"₹{booking.total_amount}"
            ] for booking in bookings]

        elif report_type == 'revenue':
            headers = ['Month', 'Total Bookings', 'Completed Bookings', 'Total Revenue']
            
            # Initialize result dict to store data by month
            result_by_month = {}
            
            # Get all bookings for this vendor
            bookings = Booking.objects.filter(vehicle__vendor=vendor)
            if start_date and end_date:
                bookings = bookings.filter(start_date__range=[start_date, end_date])
            
            # Group by month
            for booking in bookings:
                month_key = booking.start_date.strftime('%Y-%m')
                month_display = booking.start_date.strftime('%b %Y')
                
                if month_key not in result_by_month:
                    result_by_month[month_key] = {
                        'month': month_display,
                        'total_bookings': 0,
                        'completed_bookings': 0,
                        'revenue': 0
                    }
                
                result_by_month[month_key]['total_bookings'] += 1
                
                if booking.status == 'returned':
                    result_by_month[month_key]['completed_bookings'] += 1
                    result_by_month[month_key]['revenue'] += float(booking.total_amount)
            
            # Convert to table data
            table_data = [
                [
                    data['month'],
                    data['total_bookings'],
                    data['completed_bookings'],
                    f"₹{data['revenue']:.2f}"
                ]
                for month_key, data in sorted(result_by_month.items())
            ]
            
            # Add totals row
            total_bookings = sum(data['total_bookings'] for data in result_by_month.values())
            total_completed = sum(data['completed_bookings'] for data in result_by_month.values())
            total_revenue = sum(data['revenue'] for data in result_by_month.values())
            
            table_data.append(['TOTAL', total_bookings, total_completed, f"₹{total_revenue:.2f}"])

        elif report_type == 'vehicle':
            headers = ['Vehicle', 'Registration', 'Total Bookings', 'Revenue Generated', 'Average Rating']
            
            # Get all vehicles for this vendor
            vehicles = Vehicle.objects.filter(vendor=vendor)
            
            # Prepare data for each vehicle
            table_data = []
            for vehicle in vehicles:
                # Get bookings for this vehicle
                vehicle_bookings = Booking.objects.filter(vehicle=vehicle)
                if start_date and end_date:
                    vehicle_bookings = vehicle_bookings.filter(start_date__range=[start_date, end_date])
                
                # Calculate metrics
                total_bookings = vehicle_bookings.count()
                completed_bookings = vehicle_bookings.filter(status='returned')
                revenue = completed_bookings.aggregate(total=Sum('total_amount'))['total'] or 0
                avg_rating = completed_bookings.filter(feedback__isnull=False).aggregate(
                    avg=Avg('feedback__rating'))['avg'] or 0
                
                # Add to table data
                table_data.append([
                    f"{vehicle.model}",
                    f"{vehicle.registration.registration_number}",
                    total_bookings,
                    f"₹{revenue:.2f}",
                    f"{avg_rating:.1f}" if avg_rating > 0 else "No ratings"
                ])
            
            # Add totals row
            total_bookings = sum(row[2] for row in table_data)
            total_revenue = sum(float(row[3].replace('₹', '')) for row in table_data)
            
            table_data.append(['TOTAL', '', total_bookings, f"₹{total_revenue:.2f}", ''])

        # Calculate column widths more intelligently
        col_widths = []
        for i in range(len(headers)):
            max_width = len(headers[i]) * 10  # Base width on header
            for row in table_data:
                if i < len(row):  # Check if the index exists in the row
                    max_width = max(max_width, len(str(row[i])) * 10)
            col_widths.append(max_width)

        # Generate report based on format
        if file_format == 'pdf':
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            
            # Add title and date range
            title_style = getSampleStyleSheet()['Heading1']
            title_style.alignment = 1  # Center alignment
            
            subtitle_style = getSampleStyleSheet()['Normal']
            subtitle_style.alignment = 1
            
            elements.append(Paragraph(f"{report_type.title()} Report", title_style))
            elements.append(Paragraph(date_range_text, subtitle_style))
            elements.append(Spacer(1, 20))
            
            # Create the table with proper styling
            table = Table([headers] + table_data, colWidths=col_widths)
            
            # Style the table more professionally
            table_style = TableStyle([
                # Headers
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Data rows - striped for better readability
                ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # First column left aligned
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Other columns centered
                
                # Total row at the bottom
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                
                # Borders
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),  # Thicker line above totals
            ])
            
            # Add alternating row colors for better readability
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    table_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
            
            table.setStyle(table_style)
            elements.append(table)
            
            # Add footer with date and vendor information
            footer_text = f"Generated for: {vendor.business_name} on {datetime.now().strftime('%d %b %Y, %H:%M')}"
            footer_style = getSampleStyleSheet()['Normal']
            footer_style.alignment = 1  # Center alignment
            footer_style.fontSize = 8
            
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(footer_text, footer_style))
            
            # Build the PDF document
            doc.build(elements)
            pdf = buffer.getvalue()
            buffer.close()
            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
            response.write(pdf)
            return response

        elif file_format == 'excel':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xlsx"'
            
            wb = xlsxwriter.Workbook(response, {'in_memory': True})
            ws = wb.add_worksheet(f"{report_type.title()} Report")
            
            # Add title and date range
            title_format = wb.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
            subtitle_format = wb.add_format({'align': 'center', 'font_size': 12})
            
            ws.merge_range(0, 0, 0, len(headers) - 1, f"{report_type.title()} Report", title_format)
            ws.merge_range(1, 0, 1, len(headers) - 1, date_range_text, subtitle_format)
            
            # Format headers
            header_format = wb.add_format({
                'bold': True, 
                'bg_color': '#0066cc', 
                'font_color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Set column headers
            for col, header in enumerate(headers):
                ws.write(3, col, header, header_format)
                ws.set_column(col, col, max(15, len(header) * 1.2))  # Dynamic width
            
            # Format for data rows
            cell_format = wb.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
            alt_row_format = wb.add_format({'align': 'center', 'valign': 'vcenter', 'bg_color': '#f2f2f2', 'border': 1})
            
            # Special formatting for first column (left align) and currency columns
            left_align = wb.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
            alt_left_align = wb.add_format({'align': 'left', 'valign': 'vcenter', 'bg_color': '#f2f2f2', 'border': 1})
            currency_format = wb.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'num_format': '₹#,##0.00'})
            alt_currency_format = wb.add_format({'align': 'center', 'valign': 'vcenter', 'bg_color': '#f2f2f2', 'border': 1, 'num_format': '₹#,##0.00'})
            
            # Write data rows
            for row_idx, row_data in enumerate(table_data):
                # Determine if this is the totals row
                is_total_row = row_idx == len(table_data) - 1
                row_format = wb.add_format({
                    'bold': is_total_row,
                    'bg_color': '#e6e6e6' if is_total_row else ('#f2f2f2' if row_idx % 2 == 1 else 'white'),
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1,
                    'top': 2 if is_total_row else 1  # Thicker top border for total row
                })
                
                for col_idx, cell_data in enumerate(row_data):
                    # Specific formatting for different column types
                    if col_idx == 0:  # First column (vehicle or month)
                        ws.write(row_idx + 4, col_idx, cell_data, row_format)
                    elif 'Revenue' in headers[col_idx] or 'Amount' in headers[col_idx]:  # Money columns
                        # Extract numeric value from currency string if needed
                        if isinstance(cell_data, str) and cell_data.startswith('₹'):
                            value = float(cell_data.replace('₹', '').replace(',', ''))
                            ws.write_number(row_idx + 4, col_idx, value, row_format)
                        else:
                            ws.write(row_idx + 4, col_idx, cell_data, row_format)
                    else:
                        ws.write(row_idx + 4, col_idx, cell_data, row_format)
            
            # Add footer
            footer_format = wb.add_format({'align': 'center', 'font_size': 10, 'italic': True})
            footer_text = f"Generated for: {vendor.business_name} on {datetime.now().strftime('%d %b %Y, %H:%M')}"
            ws.merge_range(len(table_data) + 5, 0, len(table_data) + 5, len(headers) - 1, footer_text, footer_format)
            
            wb.close()
            return response

        elif file_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
            
            writer = csv.writer(response)
            writer.writerow([f"{report_type.title()} Report"])
            writer.writerow([date_range_text])
            writer.writerow([])  # Empty row as spacer
            writer.writerow(headers)
            writer.writerows(table_data)
            
            return response

    except Exception as e:
        logger.error(f"Error generating {report_type} report: {str(e)}", exc_info=True)
        messages.error(request, f"Error generating report: {str(e)}")
        return redirect('vendor:reports_dashboard')

    return redirect('vendor:reports_dashboard')

def chatbot_response(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        # Add your chatbot logic here
        response = {'reply': 'This is a sample response'}
        return JsonResponse(response)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@never_cache
@login_required
def track_rented_vehicles(request):
    """View for vendors to track their rented vehicles"""
    vendor = request.user.vendor  # Get the vendor associated with the user
    
    # Get active bookings for this vendor's vehicles
    active_bookings = Booking.objects.filter(
        vehicle__vendor=vendor,
        status='picked_up'
    ).select_related('user', 'vehicle')
    
    context = {
        'active_bookings': active_bookings
    }
    
    return render(request, 'vendor/track_vehicles.html', context)

@never_cache
@login_required
def vehicle_location(request, booking_id):
    """Get the latest location for a vehicle"""
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        vendor = request.user.vendor
        booking = get_object_or_404(Booking, booking_id=booking_id, vehicle__vendor=vendor)
        
        # Debug logging
        print(f"Vehicle location requested for booking {booking_id} by vendor {vendor.vendor_id}")
        
        # First try to get location through booking relationship
        latest_location = LocationShare.objects.filter(
            booking=booking
        ).order_by('-timestamp').first()
        
        # If that doesn't work, try direct SQL query by booking_id
        if not latest_location:
            print(f"No location found through relation, trying direct query by booking_id")
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, latitude, longitude, timestamp, is_live_tracking, accuracy FROM mainapp_locationshare WHERE booking_id = %s ORDER BY timestamp DESC LIMIT 1",
                        [booking_id]
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        print(f"Found location through direct query: {row}")
                        # Manually create a location object
                        class TempLocation:
                            def __init__(self, id, lat, lng, timestamp, is_live_tracking=False, accuracy=None):
                                self.id = id
                                self.latitude = lat
                                self.longitude = lng
                                self.timestamp = timestamp
                                self.is_live_tracking = is_live_tracking
                                self.accuracy = accuracy
                        
                        # Note: Adjust indices based on the query fields
                        latest_location = TempLocation(
                            row[0],  # id
                            row[1],  # lat
                            row[2],  # lng
                            row[3],  # timestamp
                            row[4] if len(row) > 4 else False,  # is_live_tracking
                            row[5] if len(row) > 5 else None    # accuracy
                        )
            except Exception as e:
                print(f"Error in direct SQL query: {str(e)}")
        
        # Third attempt: check if any customer shared their location
        if not latest_location:
            print(f"Still no location found, checking ALL customer locations")
            # Show the last 5 locations for debugging
            all_locations = LocationShare.objects.all().order_by('-timestamp')[:5]
            for loc in all_locations:
                print(f"Recent location: booking_id={loc.booking.booking_id}, lat={loc.latitude}, lng={loc.longitude}")
        
        if latest_location:
            # Debug logging for successful location
            print(f"Location found for booking {booking_id}: lat={latest_location.latitude}, lng={latest_location.longitude}")
            
            # Check if location is recent (less than 30 minutes old)
            is_recent = (timezone.now() - latest_location.timestamp) < timedelta(minutes=30)
            
            # Format the timestamp in a readable format
            formatted_timestamp = latest_location.timestamp.strftime('%b %d, %Y at %I:%M %p')
            
            # Check if this is live tracking
            is_live_tracking = hasattr(latest_location, 'is_live_tracking') and latest_location.is_live_tracking
            
            # Get accuracy if available
            accuracy = None
            if hasattr(latest_location, 'accuracy') and latest_location.accuracy is not None:
                accuracy = latest_location.accuracy
            
            location_data = {
                'latitude': latest_location.latitude,
                'longitude': latest_location.longitude,
                'timestamp': formatted_timestamp,
                'is_recent': is_recent,
                'is_live_tracking': is_live_tracking,
                'age_minutes': int((timezone.now() - latest_location.timestamp).total_seconds() / 60)
            }
            
            # Add accuracy if available
            if accuracy is not None:
                location_data['accuracy'] = round(accuracy, 2)
            
            # Get customer's phone number if available
            phone_number = "N/A"
            if hasattr(booking.user, 'profile') and booking.user.profile.phone_number:
                phone_number = booking.user.profile.phone_number
            
            return JsonResponse({
                'status': 'success',
                'location': location_data,
                'booking': {
                    'id': booking.booking_id,
                    'status': booking.status,
                    'end_date': booking.end_date.strftime('%Y-%m-%d')
                },
                'vehicle': {
                    'model': str(booking.vehicle.model),
                    'registration': booking.vehicle.registration.registration_number
                },
                'customer': {
                    'name': booking.user.get_full_name() or booking.user.username,
                    'phone': phone_number,
                    'email': booking.user.email
                }
            })
        else:
            # Debug logging for missing location
            print(f"No location data found for booking {booking_id}")
            
            return JsonResponse({
                'status': 'error',
                'message': 'No location data available for this booking',
                'booking_id': booking_id,
                'customer': {
                    'name': booking.user.get_full_name() or booking.user.username,
                    'phone': booking.user.profile.phone_number if hasattr(booking.user, 'profile') else 'N/A'
                }
            })
    except Exception as e:
        print(f"Error in vehicle_location view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'Error retrieving location: {str(e)}',
            'detail': traceback.format_exc()
        }, status=500)

@never_cache
@login_required
def accident_reports(request):
    """View for vendors to see accident reports for their vehicles"""
    vendor = request.user.vendor
    
    # Get all accident reports for this vendor's vehicles
    reports = AccidentReport.objects.filter(
        booking__vehicle__vendor=vendor
    ).select_related('booking', 'booking__user', 'booking__vehicle').order_by('-report_date')
    
    context = {
        'reports': reports,
        'emergency_reports': reports.filter(is_emergency=True, status='reported')
    }
    
    return render(request, 'vendor/accident_reports.html', context)

@never_cache
@login_required
def accident_detail(request, report_id):
    """View details of a specific accident report"""
    vendor = request.user.vendor
    report = get_object_or_404(
        AccidentReport, 
        id=report_id, 
        booking__vehicle__vendor=vendor
    )
    
    if request.method == 'POST':
        # Update the report status
        status = request.POST.get('status')
        if status in ['processing', 'resolved']:
            report.status = status
            report.save()
            
            # If resolved, notify the customer
            if status == 'resolved':
                send_accident_resolution_notification(report)
            
            return redirect('vendor:accident_reports')
    
    context = {
        'report': report,
        'booking': report.booking,
        'customer': report.booking.user,
        'vehicle': report.booking.vehicle
    }
    
    return render(request, 'vendor/accident_detail.html', context)

def send_accident_resolution_notification(report):
    """Send notification to customer about accident resolution"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings
    
    booking = report.booking
    customer_email = booking.user.email
    
    subject = f'Update on Your Accident Report for Booking #{booking.booking_id}'
    html_message = render_to_string('emails/accident_resolution.html', {
        'accident': report,
        'booking': booking,
        'customer': booking.user,
        'vehicle': booking.vehicle
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [customer_email],
        html_message=html_message,
        fail_silently=False
    )

@never_cache
@login_required
def extension_requests(request):
    """View for vendors to see booking extension records"""
    vendor = request.user.vendor
    
    # Get bookings that have been extended
    from mainapp.models import BookingExtension
    extension_requests = BookingExtension.objects.filter(
        booking__vehicle__vendor=vendor
    ).select_related('booking', 'booking__user', 'booking__vehicle').order_by('-created_at')
    
    context = {
        'extension_requests': extension_requests
    }
    
    return render(request, 'vendor/extension_requests.html', context)



