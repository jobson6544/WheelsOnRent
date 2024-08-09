from django.shortcuts import redirect
from .models import UserProfile

def check_first_login(backend, user, response, *args, **kwargs):
    if user.is_first_login:
        user.is_first_login = False
        user.save()
        return redirect('complete_profile')
    return None  # Continue with the pipeline if profile is complete