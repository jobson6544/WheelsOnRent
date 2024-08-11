import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from .models import Vendor, Vehicle, VehicleCompany, Model, Registration, Image, Features
from .forms import VehicleForm

logger = logging.getLogger(__name__)

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

@login_required
def vendor_register_profile(request):
    if request.method == 'POST':
        vendor_form = VendorProfileForm(request.POST)
        if vendor_form.is_valid():
            vendor = vendor_form.save(commit=False)
            vendor.user = request.user
            vendor.status = 'pending'
            vendor.save()
            messages.success(request, 'Vendor registration completed successfully. Your application is under review.')
            return redirect('vendor:application_under_review')
    else:
        vendor_form = VendorProfileForm()
    return render(request, 'vendor/vendor_register_profile.html', {'vendor_form': vendor_form})

@login_required
def vendor_dashboard(request):
    try:
        vendor = Vendor.objects.get(user=request.user)
    except Vendor.DoesNotExist:
        vendor = None
    return render(request, 'vendor/dashboard.html', {'vendor': vendor, 'user': request.user})

@login_required
def add_vehicle(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get or create vendor
                    vendor, created = Vendor.objects.get_or_create(user=request.user)
                    
                    # Get or create Registration
                    registration, created = Registration.objects.get_or_create(
                        registration_number=form.cleaned_data['registration_number'],
                        defaults={
                            'registration_date': form.cleaned_data['registration_date'],
                            'registration_end_date': form.cleaned_data['registration_end_date']
                        }
                    )
                    
                    if not created:
                        # Update the registration dates if it already exists
                        registration.registration_date = form.cleaned_data['registration_date']
                        registration.registration_end_date = form.cleaned_data['registration_end_date']
                        registration.save()

                    # Create Vehicle
                    vehicle = Vehicle.objects.create(
                        model=form.cleaned_data['model'],
                        vendor=vendor,
                        registration=registration,
                        rental_rate=form.cleaned_data['rental_rate'],
                        availability=form.cleaned_data['availability']
                    )

                    # Add features
                    vehicle.features.set(form.cleaned_data['features'])

                    # Handle image upload
                    if 'image' in request.FILES:
                        Image.objects.create(vehicle=vehicle, image=request.FILES['image'])

                messages.success(request, 'Vehicle added successfully.')
                return redirect('vendor:vendor_vehicles')
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
    else:
        form = VehicleForm()
    
    return render(request, 'vendor/add_vehicle.html', {'form': form})

@login_required
def vendor_vehicles(request):
    vehicles = Vehicle.objects.filter(vendor__user=request.user, status=1).select_related(
        'model__sub_category__category', 'registration'
    ).prefetch_related('features')
    for vehicle in vehicles:
        print(f"Vehicle ID: {vehicle.vehicle_id}")  # Add this line for debugging
    return render(request, 'vendor/vehicle_list.html', {'vehicles': vehicles})

@login_required
def update_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id, vendor__user=request.user, status=1)
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
        form = VehicleForm(instance=vehicle)
    return render(request, 'vendor/update_vehicle.html', {'form': form, 'vehicle': vehicle})

@login_required
def delete_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id, vendor__user=request.user)
    vehicle.status = 0
    vehicle.save()
    messages.success(request, 'Vehicle has been successfully deleted.')
    return redirect('vendor:vendor_vehicles')

@login_required
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

@login_required
def vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id, vendor__user=request.user, status=1)
    return render(request, 'vendor/vehicle_detail.html', {'vehicle': vehicle})

def application_under_review(request):
    return render(request, 'vendor/application_under_review.html')

def application_rejected(request):
    return render(request, 'vendor/application_rejected.html')

def get_companies(request, vehicle_type_id):
    companies = VehicleCompany.objects.filter(category_id=vehicle_type_id).values('sub_category_id', 'company_name')
    return JsonResponse(list(companies), safe=False)

def get_models(request, company_id):
    models = Model.objects.filter(sub_category_id=company_id).values('model_id', 'model_name')
    return JsonResponse(list(models), safe=False)