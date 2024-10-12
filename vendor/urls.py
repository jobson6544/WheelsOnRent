from django.urls import path
from . import views
from .views import VehicleDashboardView  # Add this import

app_name = 'vendor'

urlpatterns = [
    path('vendor_login/', views.vendor_login, name='vendor_login'),
    path('register/', views.vendor_register_user, name='register_user'),
    path('register/profile/', views.vendor_register_profile, name='register_profile'),
    path('dashboard/', views.vendor_dashboard, name='dashboard'),
    path('application-under-review/', views.application_under_review, name='application_under_review'),
    path('application-rejected/', views.application_rejected, name='application_rejected'),
    path('add-vehicle/', views.add_vehicle, name='add_vehicle'),
    path('api/get_companies/<int:vehicle_type_id>/', views.get_companies, name='get_companies'),
    path('api/get_models/<int:company_id>/', views.get_models, name='get_models'),
    path('vehicles/', views.vendor_vehicles, name='vendor_vehicles'),
    path('delete-vehicle/<int:vehicle_id>/', views.delete_vehicle, name='delete_vehicle'),
    path('edit-vehicle/<int:vehicle_id>/', views.edit_vehicle, name='edit_vehicle'),
    path('update-vehicle/<int:vehicle_id>/', views.update_vehicle, name='update_vehicle'),
    path('vehicle/<int:vehicle_id>/', views.vehicle_detail, name='vehicle_detail'),
    path('price-dashboard/', VehicleDashboardView.as_view(), name='price_dashboard'),
    path('profile/', views.vendor_profile, name='vendor_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('benefits/', views.vendor_benefits, name='vendor_benefits'),
]