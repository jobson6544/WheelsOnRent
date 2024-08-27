from django.urls import path
from . import views

app_name = 'adminapp'

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('vehicle-management/', views.vehicle_management, name='vehicle_management'),
    path('add-vehicle-type/', views.add_vehicle_type, name='add_vehicle_type'),
    path('add-vehicle-company/', views.add_vehicle_company, name='add_vehicle_company'),
    path('add-model/', views.add_model, name='add_model'),
    path('add-features/', views.add_features, name='add_features'),
    path('toggle-vehicle-type/<int:id>/', views.toggle_vehicle_type, name='toggle_vehicle_type'),
    path('toggle-vehicle-company/<int:id>/', views.toggle_vehicle_company, name='toggle_vehicle_company'),
    path('toggle-model/<int:id>/', views.toggle_model, name='toggle_model'),
    path('toggle-features/<int:id>/', views.toggle_features, name='toggle_features'),
    path('vendor-success/', views.vendor_success, name='vendor_success'),
    path('manage-vendor-applications/', views.manage_vendor_applications, name='manage_vendor_applications'),
    path('approve-vendor/<int:vendor_id>/', views.approve_vendor, name='approve_vendor'),
    path('reject-vendor/<int:vendor_id>/', views.reject_vendor, name='reject_vendor'),
]