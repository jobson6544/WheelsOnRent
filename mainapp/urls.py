from django.urls import path, include
from . import views

app_name = 'mainapp'

urlpatterns = [
    path('',views.index,name='index'),
    path('user_login/',views.login_view,name='user_login'),
    path('user_register/',views.customer_register,name='user_register'),
    path('complete_profile/', views.complete_profile, name='complete_profile'),
    path('success/', views.success, name='success'),
    path('home/', views.home, name='home'),
    path('profile/', views.profile_view, name='profile_view'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('book/<int:id>/', views.book_vehicle, name='book_vehicle'),
    path('booking-history/', views.user_booking_history, name='user_booking_history'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('payment/', views.payment_view, name='payment'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-cancelled/', views.payment_cancelled, name='payment_cancelled'),
    path('payment-error/', views.payment_error, name='payment_error'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('benefits/', views.vendor_benefits, name='vendor_benefits'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('password-reset-verify/', views.password_reset_verify, name='password_reset_verify'),
    path('bookings/', views.user_bookings, name='user_bookings'),
    path('booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('submit-feedback/<int:booking_id>/', views.submit_feedback, name='submit_feedback'),
    path('chatbot/response/', views.chatbot_response, name='chatbot_response'),
    path('chatbot/message/', views.chatbot_message, name='chatbot_message'),
    
    # New URL patterns for current rental management
    path('my-rentals/', views.current_rentals, name='current_rentals'),
    path('rental/<int:booking_id>/', views.rental_details, name='rental_details'),
    path('rental/<int:booking_id>/early-return/', views.early_return, name='early_return'),
    path('rental/<int:booking_id>/report-accident/', views.report_accident, name='report_accident'),
    path('rental/<int:booking_id>/share-location/', views.share_location, name='share_location'),
    path('rental/<int:booking_id>/share-location-test/', views.share_location_test, name='share_location_test'),
    path('rental/<int:booking_id>/check-extension/', views.check_extension, name='check_extension'),
    path('rental/<int:booking_id>/process-extension/', views.process_extension, name='process_extension'),
    path('extension-success/', views.extension_success, name='extension_success'),
]
