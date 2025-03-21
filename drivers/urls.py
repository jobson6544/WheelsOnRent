from django.urls import path
from . import views

app_name = 'drivers'

urlpatterns = [
    # Authentication URLs
    path('login/', views.driver_login, name='driver_login'),
    path('register/', views.register_driver, name='register_driver'),
    path('logout/', views.driver_logout, name='driver_logout'),
    
    # Main URLs
    path('dashboard/', views.driver_dashboard, name='dashboard'),
    path('profile/', views.driver_profile, name='profile'),
    path('settings/', views.driver_settings, name='settings'),
    path('support/', views.driver_support, name='support'),
    
    # Trips URLs
    path('trips/', views.driver_trips, name='trips'),
    path('trips/active/', views.active_trips, name='active_trips'),
    path('trips/completed/', views.completed_trips, name='completed_trips'),
    
    # Earnings URLs
    path('earnings/', views.driver_earnings, name='earnings'),
    path('earnings/history/', views.earnings_history, name='earnings_history'),
    
    # Booking URLs
    path('book/<int:driver_id>/', views.book_driver, name='book_driver'),
    path('book/<int:driver_id>/specific-date/', views.book_driver, {'booking_type': 'specific_date'}, name='book_driver_specific_date'),
    path('book/<int:driver_id>/point-to-point/', views.book_driver, {'booking_type': 'point_to_point'}, name='book_driver_point_to_point'),
    path('book/<int:driver_id>/with-vehicle/', views.book_driver, {'booking_type': 'with_vehicle'}, name='book_driver_with_vehicle'),
    path('booking/success/', views.driver_booking_success, name='driver_booking_success'),
    path('booking/cancel/', views.driver_booking_cancel, name='driver_booking_cancel'),
    path('booking/list/', views.driver_booking_list, name='driver_booking_list'),
    
    # Trip management URLs
    path('trip/<int:booking_id>/start/', views.start_trip, name='start_trip'),
    path('trip/<int:booking_id>/end/', views.end_trip, name='end_trip'),
    path('check-availability/<int:driver_id>/', views.check_driver_availability, name='check_driver_availability'),
    path('start-trip/<int:booking_id>/', views.start_trip, name='start_trip'),
    path('verify-trip-otp/<int:booking_id>/', views.verify_trip_otp, name='verify_trip_otp'),
    
    # Other URLs
    path('documents/', views.documents, name='documents'),
    path('approval-status/', views.approval_status, name='approval_status'),
    path('update-status/', views.update_status, name='update_status'),
    path('change-password/', views.change_password, name='change_password'),
    path('settings/update/', views.update_settings, name='update_settings'),
    path('settings/privacy/update/', views.update_privacy, name='update_privacy'),
    path('settings/account/update/', views.update_account, name='update_account'),
]
