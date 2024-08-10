from django.urls import path, include
from . import views

urlpatterns = [
    path('',views.index,name='index'),
    path('user_login/',views.login_view,name='user_login'),
    path('user_register/',views.customer_register,name='user_register'),
    path('complete_profile/', views.complete_profile, name='complete_profile'),
    path('success/', views.success, name='success'),
    path('home/', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),
]