from django.urls import path
from . import views

app_name = 'vendor'

urlpatterns = [
    path('vendor_login/', views.vendor_login, name='vendor_login'),
    path('register/', views.vendor_register_user, name='register_user'),
    path('register/profile/', views.vendor_register_profile, name='register_profile'),
    path('dashboard/', views.vendor_dashboard, name='dashboard'),
    path('application-under-review/', views.application_under_review, name='application_under_review'),
    path('application-rejected/', views.application_rejected, name='application_rejected'),
]