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
    path('book/<int:vehicle_id>/', views.book_vehicle, name='book_vehicle'),
    path('booking-history/', views.user_booking_history, name='user_booking_history'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]