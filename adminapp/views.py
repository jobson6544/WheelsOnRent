from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404  # Add this import
from django.contrib import messages
from .forms import VehicleTypeForm, VehicleCompanyForm, ModelForm, FeaturesForm
from vendor.models import VehicleType, VehicleCompany, Model, Features, Vendor, Vehicle  # Add this import for the Vehicle model
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
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse
from django.http import HttpResponse
from mainapp.models import Feedback
from django.db.models import Q
from django.core.paginator import PageNotAnInteger, EmptyPage
from mainapp.models import Booking
from django.http import HttpResponseNotAllowed
import csv
from datetime import datetime
import xlsxwriter
from io import BytesIO
from mainapp.models import Booking  # Ensure Booking model is imported
from django.db.models import Count
from django.utils import timezone
from drivers.models import Driver, DriverAuth, DriverDocument, DriverApplicationLog
from django.db import models

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
    vehicle_types = VehicleType.objects.all()
    context = {
        'vehicle_type_form': VehicleTypeForm(),
        'vehicle_types': vehicle_types,
        }
    if request.method == 'POST':
        form = VehicleTypeForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'adminapp/add_vehicle_type.html', context)


def add_vehicle_company(request):
    vehicle_types = VehicleType.objects.all()
    vehicle_companies = VehicleCompany.objects.all()
    context = {
        'vehicle_company_form': VehicleCompanyForm(),
        'vehicle_companies': vehicle_companies,
        }
    if request.method == 'POST':
        form = VehicleCompanyForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'adminapp/add_vehicle_company.html', context)

def add_model(request):
    models = Model.objects.all()
    context = {
        'model_form': ModelForm(),
        'models': models,
    }
    if request.method == 'POST':
        form = ModelForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'adminapp/add_model.html', context)

def add_features(request):
    features = Features.objects.all()
    context = {
        'features_form': FeaturesForm(),
        'features': features,
    }
    if request.method == 'POST':
        form = FeaturesForm(request.POST)
        if form.is_valid():
            form.save()
    return render(request, 'adminapp/add_features.html', context)

def toggle_vehicle_type(request, id):
    vehicle_type = get_object_or_404(VehicleType, category_id=id)
    if request.method == 'POST':
        vehicle_type.is_active = not vehicle_type.is_active
        vehicle_type.save()
        return redirect('adminapp:toggle_vehicle_type')
    return render(request, 'adminapp/add_vehicle_type.html')

def toggle_vehicle_company(request, id):
    if request.method == 'POST':
        vehicle_company = VehicleCompany.objects.get(sub_category_id=id)
        vehicle_company.is_active = not vehicle_company.is_active
        vehicle_company.save()
        return redirect('adminapp:toggle_vehicle_company')
    return render(request, 'adminapp/add_vehicle_company.html')

def toggle_model(request, id):
    if request.method == 'POST':
        model = Model.objects.get(model_id=id)
        model.is_active = not model.is_active
        model.save()
        return redirect('adminapp:toggle_model')
    return render(request, 'adminapp/add_model.html')
            

def toggle_features(request, id):
    if request.method == 'POST':
        feature = Features.objects.get(feature_id=id)
        feature.is_active = not feature.is_active
        feature.save()
        return redirect('adminapp:toggle_features')
    return render(request, 'adminapp/add_features.html')

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
    return redirect('index')
@user_passes_test(is_admin, login_url='adminapp:login')
def admin_dashboard(request):
    # Fetch all bookings with related data
    bookings = Booking.objects.select_related('user', 'vehicle', 'vehicle__vendor').order_by('-start_date')

    # Fetch top renting vehicles (you may need to adjust the logic based on your model)
    top_renting_vehicles = Vehicle.objects.annotate(
        times_rented=Count('bookings')  # Assuming you have a related name 'bookings' in Vehicle model
    ).order_by('-times_rented')[:5]  # Get top 5 renting vehicles

    context = {
        'bookings': bookings,
        'customers': User.objects.filter(role='user', is_active=True),
        'vehicles': Vehicle.objects.all(),  # Assuming you have a Vehicle model
        'top_renting_vehicles': top_renting_vehicles,  # Add this line
    }
    
    return render(request, 'adminapp/admin_dashboard.html', context)

# Use this decorator for all admin views
def admin_required(view_func):
    decorated_view_func = user_passes_test(is_admin, login_url='adminapp:login')(view_func)
    return decorated_view_func


@staff_member_required(login_url='adminapp:login')
def manage_vendor_applications(request):
    pending_vendors = Vendor.objects.filter(status='pending')
    return render(request, 'adminapp/manage_vendor_applications.html', {'pending_vendors': pending_vendors})

@staff_member_required(login_url='adminapp:login')
def approve_vendor(request, vendor_id):
    try:
        vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
        
        vendor.status = 'approved'
        vendor.save()

        try:
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
            print("Approval email sent successfully")
        except Exception as e:
            print(f"Error sending approval email: {str(e)}")
            messages.error(request, f"Error sending approval email: {str(e)}")

        messages.success(request, f"Vendor {vendor.business_name} has been approved and notified via email.")
        return redirect('adminapp:manage_vendor_applications')
    except Vendor.DoesNotExist:
        messages.error(request, "Vendor not found.")
        return redirect('adminapp:manage_vendor_applications')
    except Exception as e:
        print(f"Error in approve_vendor: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return HttpResponse("An error occurred while processing your request.", status=500)

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



@login_required
def active_customers(request):
    customers = User.objects.filter(role='user', is_active=True).order_by('-date_joined')
    
    paginator = Paginator(customers, 20)  # Show 20 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customers': page_obj,
        'total_customers': customers.count(),
    }
    
    return render(request, 'adminapp/active_customers.html', context)

@login_required
def deactivate_customer(request, user_id):
    customer = get_object_or_404(User, id=user_id, role='user')
    if request.method == 'POST':
        customer.is_active = False
        customer.save()
        
        # Send email notification
        subject = 'Your account has been deactivated'
        html_message = render_to_string('adminapp/email/account_deactivated.html', {'user': customer})
        plain_message = strip_tags(html_message)
        from_email = settings.EMAIL_HOST_USER
        to_email = customer.email
        
        try:
            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
            messages.success(request, f"Customer {customer.full_name} has been deactivated and notified via email.")
        except Exception as e:
            messages.warning(request, f"Customer {customer.full_name} has been deactivated, but there was an error sending the email notification.")
            print(f"Email sending error: {str(e)}")
        
        return redirect('adminapp:active_customers')
    return redirect('adminapp:active_customers')

@login_required
def deactivated_customers(request):
    customers = User.objects.filter(role='user', is_active=False).order_by('-date_joined')
    
    paginator = Paginator(customers, 20)  # Show 20 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customers': page_obj,
        'total_customers': customers.count(),
    }
    
    return render(request, 'adminapp/deactivated_customers.html', context)

@login_required
def reactivate_customer(request, user_id):
    customer = get_object_or_404(User, id=user_id, role='user')
    if request.method == 'POST':
        customer.is_active = True
        customer.save()
        
        # Send email notification
        subject = 'Your account has been reactivated'
        html_message = render_to_string('adminapp/email/account_reactivated.html', {'user': customer})
        plain_message = strip_tags(html_message)
        from_email = settings.EMAIL_HOST_USER
        to_email = customer.email
        
        try:
            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
            messages.success(request, f"Customer {customer.full_name} has been reactivated and notified via email.")
        except Exception as e:
            messages.warning(request, f"Customer {customer.full_name} has been reactivated, but there was an error sending the email notification.")
            print(f"Email sending error: {str(e)}")
        
        return redirect('adminapp:deactivated_customers')
    return redirect('adminapp:deactivated_customers')

@login_required
def all_customers(request):
    customers = User.objects.filter(role='user').order_by('-date_joined')
    
    paginator = Paginator(customers, 20)  # Show 20 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customers': page_obj,
        'total_customers': customers.count(),
    }
    
    return render(request, 'adminapp/all_customers.html', context)

@login_required
def toggle_customer_status(request, user_id):
    customer = get_object_or_404(User, id=user_id, role='user')
    if request.method == 'POST':
        customer.is_active = not customer.is_active
        customer.save()
        
        # Prepare email notification
        if customer.is_active:
            subject = 'Your account has been reactivated'
            template = 'adminapp/email/account_reactivated.html'
            success_message = f"Customer {customer.full_name} has been reactivated and notified via email."
        else:
            subject = 'Your account has been deactivated'
            template = 'adminapp/email/account_deactivated.html'
            success_message = f"Customer {customer.full_name} has been deactivated and notified via email."
        
        html_message = render_to_string(template, {'user': customer})
        plain_message = strip_tags(html_message)
        from_email = settings.EMAIL_HOST_USER
        to_email = customer.email
        
        try:
            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
            messages.success(request, success_message)
        except Exception as e:
            messages.warning(request, f"Customer status changed, but there was an error sending the email notification.")
            print(f"Email sending error: {str(e)}")
        
        return redirect('adminapp:all_customers')
    return redirect('adminapp:all_customers')

@login_required
@user_passes_test(is_admin)
def view_all_feedback(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')
    
    # Filter by vendor if specified
    vendor_id = request.GET.get('vendor')
    if vendor_id:
        feedbacks = feedbacks.filter(booking__vehicle__vendor_id=vendor_id)
    
    # Filter by rating if specified
    rating = request.GET.get('rating')
    if rating:
        feedbacks = feedbacks.filter(rating=rating)
    
    paginator = Paginator(feedbacks, 20)
    page = request.GET.get('page')
    feedbacks_page = paginator.get_page(page)
    
    context = {
        'feedbacks': feedbacks_page,
        'vendors': Vendor.objects.all(),
        'selected_vendor': vendor_id,
        'selected_rating': rating
    }
    return render(request, 'adminapp/feedback_list.html', context)

@staff_member_required(login_url='adminapp:login')
def all_bookings(request):
    # Get all bookings with related data
    bookings = Booking.objects.select_related(
        'user', 
        'vehicle', 
        'vehicle__vendor'
    ).order_by('-start_date')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        bookings = bookings.filter(
            Q(user__full_name__icontains=search_query) |
            Q(vehicle__vendor__business_name__icontains=search_query) |
            Q(booking_id__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    
    # Filter by date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        bookings = bookings.filter(
            start_date__gte=start_date,
            end_date__lte=end_date
        )
    
    # Pagination
    paginator = Paginator(bookings, 20)  # Show 20 bookings per page
    page = request.GET.get('page')
    try:
        bookings_page = paginator.page(page)
    except PageNotAnInteger:
        bookings_page = paginator.page(1)
    except EmptyPage:
        bookings_page = paginator.page(paginator.num_pages)
    
    context = {
        'bookings': bookings_page,
        'search_query': search_query,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'status_choices': Booking.STATUS_CHOICES,
    }
    
    return render(request, 'adminapp/all_bookings.html', context)

@staff_member_required(login_url='adminapp:login')
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related(
        'user',
        'vehicle',
        'vehicle__vendor',
        'pickup',
        'vehicle_return'
    ), booking_id=booking_id)
    
    context = {
        'booking': booking,
        'customer': booking.user,
        'vendor': booking.vehicle.vendor,
        'vehicle': booking.vehicle,
        'pickup': booking.pickup if hasattr(booking, 'pickup') else None,
        'return_details': booking.vehicle_return if hasattr(booking, 'vehicle_return') else None,
    }
    
    return render(request, 'adminapp/booking_detail.html', context)

@staff_member_required(login_url='adminapp:login')
def export_bookings(request):
    response = None
    bookings = Booking.objects.select_related(
        'user',
        'vehicle',
        'vehicle__vendor'
    ).all()

    export_format = request.GET.get('format', 'csv')

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bookings_export_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'Booking ID',
            'Customer Name',
            'Customer Email',
            'Vehicle',
            'Vendor',
            'Start Date',
            'End Date',
            'Total Amount',
            'Status',
            'Created At'
        ])

        # Write data
        for booking in bookings:
            writer.writerow([
                booking.booking_id,
                booking.user.get_full_name(),
                booking.user.email,
                str(booking.vehicle.model),
                booking.vehicle.vendor.business_name,
                booking.start_date.strftime('%Y-%m-%d'),
                booking.end_date.strftime('%Y-%m-%d'),
                booking.total_amount,
                booking.get_status_display(),
                booking.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

    elif export_format == 'excel':
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Add headers
        headers = [
            'Booking ID',
            'Customer Name',
            'Customer Email',
            'Vehicle',
            'Vendor',
            'Start Date',
            'End Date',
            'Total Amount',
            'Status',
            'Created At'
        ]

        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f0f0f0',
            'border': 1
        })

        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        for row, booking in enumerate(bookings, start=1):
            worksheet.write(row, 0, booking.booking_id)
            worksheet.write(row, 1, booking.user.get_full_name())
            worksheet.write(row, 2, booking.user.email)
            worksheet.write(row, 3, str(booking.vehicle.model))
            worksheet.write(row, 4, booking.vehicle.vendor.business_name)
            worksheet.write(row, 5, booking.start_date.strftime('%Y-%m-%d'))
            worksheet.write(row, 6, booking.end_date.strftime('%Y-%m-%d'))
            worksheet.write(row, 7, float(booking.total_amount))
            worksheet.write(row, 8, booking.get_status_display())
            worksheet.write(row, 9, booking.created_at.strftime('%Y-%m-%d %H:%M:%S'))

        # Adjust column widths
        for col in range(len(headers)):
            worksheet.set_column(col, col, 15)

        workbook.close()
        
        # Create the HttpResponse
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="bookings_export_{datetime.now().strftime("%Y%m%d")}.xlsx"'

    return response

@staff_member_required(login_url='adminapp:login')
def cancel_booking(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, f'Booking #{booking_id} has been cancelled.')
        return redirect('adminapp:booking_detail', booking_id=booking_id)
    return HttpResponseNotAllowed(['POST'])

@staff_member_required(login_url='adminapp:login')
def update_booking_status(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        new_status = request.POST.get('status')
        if new_status in dict(Booking.STATUS_CHOICES):
            booking.status = new_status
            booking.save()
            messages.success(request, f'Booking #{booking_id} status updated to {booking.get_status_display()}')
        else:
            messages.error(request, 'Invalid status provided')
        return redirect('adminapp:booking_detail', booking_id=booking_id)
    return HttpResponseNotAllowed(['POST'])

@staff_member_required(login_url='adminapp:login')
def create_booking(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        vehicle_id = request.POST.get('vehicle')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Create a new booking
        booking = Booking(
            user_id=customer_id,
            vehicle_id=vehicle_id,
            start_date=start_date,
            end_date=end_date,
            total_amount=0,  # Set this based on your business logic
            status='confirmed'  # Set default status
        )
        booking.save()
        messages.success(request, 'Booking created successfully.')
        return redirect('adminapp:admin_dashboard')  # Redirect to the dashboard

    # If GET request, render the dashboard with necessary context
    customers = User.objects.filter(role='user', is_active=True)
    vehicles = Vehicle.objects.all()  # Assuming you have a Vehicle model
    return render(request, 'adminapp/admin_dashboard.html', {
        'customers': customers,
        'vehicles': vehicles,
    })

@staff_member_required(login_url='adminapp:login')
def pending_drivers(request):
    drivers = Driver.objects.filter(status='pending_approval').order_by('-id')
    paginator = Paginator(drivers, 10)
    page = request.GET.get('page')
    drivers = paginator.get_page(page)
    
    return render(request, 'adminapp/drivers/driver_list.html', {
        'drivers': drivers,
        'section': 'pending'
    })

@staff_member_required(login_url='adminapp:login')
def approved_drivers(request):
    drivers = Driver.objects.filter(status='approved').order_by('-approved_at')
    paginator = Paginator(drivers, 10)
    page = request.GET.get('page')
    drivers = paginator.get_page(page)
    
    return render(request, 'adminapp/drivers/driver_list.html', {
        'drivers': drivers,
        'section': 'approved'
    })

@staff_member_required(login_url='adminapp:login')
def rejected_drivers(request):
    drivers = Driver.objects.filter(status='rejected').order_by('-id')
    paginator = Paginator(drivers, 10)
    page = request.GET.get('page')
    drivers = paginator.get_page(page)
    
    return render(request, 'adminapp/drivers/driver_list.html', {
        'drivers': drivers,
        'section': 'rejected'
    })

@staff_member_required(login_url='adminapp:login')
def all_drivers(request):
    drivers = Driver.objects.all().order_by('-id')
    paginator = Paginator(drivers, 10)
    page = request.GET.get('page')
    drivers = paginator.get_page(page)
    
    return render(request, 'adminapp/drivers/driver_list.html', {
        'drivers': drivers,
        'section': 'all'
    })

@staff_member_required(login_url='adminapp:login')
def view_driver_details(request, driver_id):
    driver = get_object_or_404(Driver, id=driver_id)
    documents = DriverDocument.objects.filter(driver=driver)
    application_logs = DriverApplicationLog.objects.filter(driver=driver).order_by('-timestamp')
    
    # Check if all required documents are verified
    all_documents_verified = documents.exists() and all(doc.is_verified for doc in documents)
    
    return render(request, 'adminapp/drivers/driver_details.html', {
        'driver': driver,
        'documents': documents,
        'application_logs': application_logs,
        'all_documents_verified': all_documents_verified
    })

@staff_member_required(login_url='adminapp:login')
def approve_driver(request, driver_id):
    driver = get_object_or_404(Driver, id=driver_id)
    documents = DriverDocument.objects.filter(driver=driver)
    
    # Check if all required documents are verified
    if not all(doc.is_verified for doc in documents):
        messages.error(request, 'All documents must be verified before approving the driver')
        return redirect('adminapp:view_driver_details', driver_id=driver.id)
    
    if request.method == 'POST':
        driver.status = 'approved'
        driver.approved_at = timezone.now()
        driver.approved_by = request.user
        driver.save()
        
        # Create application log
        DriverApplicationLog.objects.create(
            driver=driver,
            admin=request.user,
            action='approve',
            notes=request.POST.get('notes', '')
        )
        
        # Send email notification
        try:
            driver.send_approval_email()
            messages.success(request, f'Driver {driver.full_name} has been approved and notified')
        except Exception as e:
            messages.warning(request, f'Driver approved but email notification failed: {str(e)}')
        
        return redirect('adminapp:pending_drivers')
    
    return render(request, 'adminapp/drivers/approve_driver.html', {'driver': driver})

@staff_member_required(login_url='adminapp:login')
def reject_driver(request, driver_id):
    driver = get_object_or_404(Driver, id=driver_id)
    if request.method == 'POST':
        driver.status = 'rejected'
        driver.save()
        
        # Create application log
        DriverApplicationLog.objects.create(
            driver=driver,
            admin=request.user,
            action='reject',
            notes=request.POST.get('notes', '')
        )
        
        # Send email notification
        try:
            subject = 'Your Driver Application Status'
            html_message = render_to_string('adminapp/email/driver_rejected.html', {
                'driver': driver,
                'reason': request.POST.get('notes', '')
            })
            plain_message = strip_tags(html_message)
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [driver.auth.email],
                html_message=html_message
            )
        except Exception as e:
            messages.warning(request, f'Driver rejected but email notification failed: {str(e)}')
        else:
            messages.success(request, f'Driver {driver.full_name} has been rejected and notified')
        
        return redirect('adminapp:pending_drivers')
    
    return render(request, 'adminapp/drivers/reject_driver.html', {'driver': driver})

@staff_member_required(login_url='adminapp:login')
def view_driver_document(request, document_id):
    try:
        document = get_object_or_404(DriverDocument, id=document_id)
        
        # Check if file exists and get its path
        if document.document and hasattr(document.document, 'path'):
            file_path = document.document.path
            
            if os.path.exists(file_path):
                # Determine content type based on file extension
                content_type = 'application/pdf'  # Default to PDF
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    content_type = 'image/jpeg'
                elif file_path.lower().endswith('.pdf'):
                    content_type = 'application/pdf'
                
                response = FileResponse(open(file_path, 'rb'), content_type=content_type)
                # Set content disposition to inline for viewing in browser
                response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
                return response
            
        raise Http404("Document not found")
    except Exception as e:
        logger.error(f"Error viewing document {document_id}: {str(e)}")
        messages.error(request, f'Error viewing document: {str(e)}')
        return redirect('adminapp:view_driver_details', driver_id=document.driver.id)

@staff_member_required(login_url='adminapp:login')
def verify_driver_document(request, document_id):
    document = get_object_or_404(DriverDocument, id=document_id)
    document.is_verified = True
    document.save()
    
    messages.success(request, f'{document.get_document_type_display()} has been verified')
    return redirect('adminapp:view_driver_details', driver_id=document.driver.id)




