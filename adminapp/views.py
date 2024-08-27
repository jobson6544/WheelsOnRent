from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse  # Add this import
from django.contrib import messages
from .forms import VehicleTypeForm, VehicleCompanyForm, ModelForm, FeaturesForm
from vendor.models import VehicleType, VehicleCompany, Model, Features, Vendor
from django.template.loader import render_to_string  # Add this import
import os
from django.conf import settings
from django.template.loader import get_template
from django.utils.html import strip_tags  # Add this import
from django.core.mail import send_mail  # Add this import
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

def vehicle_management(request):
    vehicle_types = VehicleType.objects.all()
    vehicle_companies = VehicleCompany.objects.all()
    models = Model.objects.all()
    features = Features.objects.all()

    context = {
        'vehicle_type_form': VehicleTypeForm(),
        'vehicle_company_form': VehicleCompanyForm(),
        'model_form': ModelForm(),
        'features_form': FeaturesForm(),
        'vehicle_types': vehicle_types,
        'vehicle_companies': vehicle_companies,
        'models': models,
        'features': features,
    }
    print("Context data:", context)  # Add this line to debug
    return render(request, 'adminapp/vehicle_management.html', context)

def add_vehicle_type(request):
    if request.method == 'POST':
        form = VehicleTypeForm(request.POST)
        if form.is_valid():
            vehicle_type = form.save()
            return JsonResponse({'success': True, 'category_id': vehicle_type.category_id, 'category_name': vehicle_type.category_name})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'errors': 'Invalid request method'})

def add_vehicle_company(request):
    if request.method == 'POST':
        form = VehicleCompanyForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('adminapp:vehicle_management')
    return vehicle_management(request)

def add_model(request):
    if request.method == 'POST':
        form = ModelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('adminapp:vehicle_management')
    return vehicle_management(request)

def add_features(request):
    if request.method == 'POST':
        form = FeaturesForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('adminapp:vehicle_management')
    return vehicle_management(request)

def toggle_vehicle_type(request, id):
    vehicle_type = get_object_or_404(VehicleType, category_id=id)
    if request.method == 'POST':
        vehicle_type.is_active = not vehicle_type.is_active
        vehicle_type.save()
        return redirect('adminapp:vehicle_management')
    return render(request, 'adminapp/vehicle_management.html')

def toggle_vehicle_company(request, id):
    if request.method == 'POST':
        try:
            vehicle_company = VehicleCompany.objects.get(sub_category_id=id)
            vehicle_company.is_active = not vehicle_company.is_active
            vehicle_company.save()
            return JsonResponse({
                'success': True,
                'is_active': vehicle_company.is_active
            })
        except VehicleCompany.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Vehicle company not found'
            })
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def toggle_model(request, id):
    if request.method == 'POST':
        try:
            model = Model.objects.get(model_id=id)
            model.is_active = not model.is_active
            model.save()
            return JsonResponse({
                'success': True,
                'is_active': model.is_active
            })
        except Model.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Model not found'
            })
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def toggle_features(request, id):
    if request.method == 'POST':
        try:
            feature = Features.objects.get(feature_id=id)
            feature.is_active = not feature.is_active
            feature.save()
            return JsonResponse({
                'success': True,
                'is_active': feature.is_active
            })
        except Features.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Feature not found'
            })
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def vendor_success(request):
    return render(request, 'adminapp/success.html')

def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')  # Changed from username to email
        password = request.POST.get('password')
        
        logger.info(f"Login attempt for email: {email}")
        
        try:
            user = User.objects.get(email=email, role='admin')
            logger.info(f"User found: {user.email}, role: {user.role}")
            
            # Use Django's authenticate function
            authenticated_user = authenticate(request, username=email, password=password)
            
            if authenticated_user is not None:
                login(request, authenticated_user)
                logger.info(f"User {user.email} logged in successfully")
                if user.is_first_login:
                    user.is_first_login = False
                    user.save()
                    return redirect('adminapp:change_password')  # Redirect to change password on first login
                return redirect('adminapp:dashboard')
            else:
                logger.warning(f"Invalid password for user: {user.email}")
                messages.error(request, 'Invalid password')
        except User.DoesNotExist:
            logger.warning(f"No admin user found for email: {email}")
            messages.error(request, 'Invalid email or not an admin user')
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            messages.error(request, 'An unexpected error occurred. Please try again.')
    
    return render(request, 'adminapp/login.html')

def admin_logout(request):
    logout(request)
    return redirect('adminapp:login')
@user_passes_test(is_admin, login_url='adminapp:login')
def admin_dashboard(request):
    return render(request, 'adminapp/admin_dashboard.html')  # Note the change here

# Use this decorator for all admin views
def admin_required(view_func):
    decorated_view_func = user_passes_test(is_admin, login_url='adminapp:login')(view_func)
    return decorated_view_func

@admin_required
def some_admin_view(request):
    # Your view logic here
    pass
@staff_member_required(login_url='adminapp:login')
def manage_vendor_applications(request):
    pending_vendors = Vendor.objects.filter(status='pending')
    return render(request, 'adminapp/manage_vendor_applications.html', {'pending_vendors': pending_vendors})

@staff_member_required(login_url='adminapp:login')
def approve_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    vendor.status = 'approved'
    vendor.save()

    # Send approval email
    subject = 'Your Vendor Application Has Been Approved'
    html_message = render_to_string('adminapp/email/vendor_approval.html', {'vendor': vendor})
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = vendor.user.email

    send_mail(
        subject,
        plain_message,
        from_email,
        [to_email],
        html_message=html_message,
        fail_silently=False,
    )

    messages.success(request, f"Vendor {vendor.business_name} has been approved and notified via email.")
    return redirect('adminapp:manage_vendor_applications')

@staff_member_required(login_url='adminapp:login')
def reject_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    vendor.status = 'rejected'
    vendor.save()

    try:
        # Send rejection email
        subject = 'Update on Your Vendor Application'
        html_message = render_to_string('adminapp/email/vendor_rejection.html', {'vendor': vendor})
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = vendor.user.email

        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        print("Rejection email sent successfully")
    except Exception as e:
        print(f"Error sending rejection email: {str(e)}")
        messages.error(request, f"Error sending rejection email: {str(e)}")

    messages.success(request, f"Vendor {vendor.business_name} has been rejected and notified via email.")
    return redirect('adminapp:manage_vendor_applications')

@staff_member_required(login_url='adminapp:login')
def active_vendors(request):
    active_vendors = Vendor.objects.filter(status='approved')
    return render(request, 'adminapp/active_vendors.html', {'active_vendors': active_vendors})

@staff_member_required(login_url='adminapp:login')
def deactivate_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    vendor.status = 'deactivated'
    vendor.save()

    try:
        # Send deactivation email
        subject = 'Your Vendor Account Has Been Deactivated'
        html_message = render_to_string('adminapp/email/vendor_deactivation.html', {'vendor': vendor})
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = vendor.user.email

        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        print("Deactivation email sent successfully")
    except Exception as e:
        print(f"Error sending deactivation email: {str(e)}")
        messages.error(request, f"Error sending deactivation email: {str(e)}")

    messages.success(request, f"Vendor {vendor.business_name} has been deactivated and notified via email.")
    return redirect('adminapp:active_vendors')

@staff_member_required(login_url='adminapp:login')
def deactivated_vendors(request):
    deactivated_vendors = Vendor.objects.filter(status='deactivated')
    return render(request, 'adminapp/deactivated_vendors.html', {'deactivated_vendors': deactivated_vendors})

@staff_member_required(login_url='adminapp:login')
def activate_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    vendor.status = 'approved'
    vendor.save()

    try:
        # Send activation email
        subject = 'Your Vendor Account Has Been Reactivated'
        html_message = render_to_string('adminapp/email/vendor_reactivation.html', {'vendor': vendor})
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = vendor.user.email

        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        print("Reactivation email sent successfully")
    except Exception as e:
        print(f"Error sending reactivation email: {str(e)}")
        messages.error(request, f"Error sending reactivation email: {str(e)}")

    messages.success(request, f"Vendor {vendor.business_name} has been reactivated and notified via email.")
    return redirect('adminapp:deactivated_vendors')

@staff_member_required(login_url='adminapp:login')
def all_vendors(request):
    vendors = Vendor.objects.all().order_by('status', 'business_name')
    return render(request, 'adminapp/all_vendors.html', {'vendors': vendors})

@admin_required
def all_vendors(request):
    vendors = Vendor.objects.all().order_by('status', 'business_name')
    return render(request, 'adminapp/all_vendors.html', {'vendors': vendors})

@admin_required
def approve_vendor(request, vendor_id):
    # Your view logic here
    pass

# Apply this to all your admin views

