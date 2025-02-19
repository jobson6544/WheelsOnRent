from django.urls import path, include
from . import views


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
]
