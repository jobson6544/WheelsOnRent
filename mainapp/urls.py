from django.urls import path, include
from . import views

urlpatterns = [
    path('',views.index,name='index'),
    path('user_login/',views.login_view,name='user_login'),
    path('vendor-login/', views.vendor_login, name='vendor_login'),
    path('user_register/',views.customer_register,name='user_register'),
    path('complete_profile/', views.complete_profile, name='complete_profile'),
    path('success/', views.success, name='success'),
    path('home/', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),  # Added this line for logout
    path('vendor_success/', views.vendor_success, name='vendor_success'),
    path('vendor-register/', views.vendor_register_user, name='vendor_register_user'),
    path('vendor-register/profile/', views.vendor_register_profile, name='vendor_register_profile'),
    path('vendor-register/profile/vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
]