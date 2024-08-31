from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

def vendor_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url='vendor:vendor_login'):
    """
    Decorator for views that checks that the user is a vendor,
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and hasattr(u, 'vendor') and u.vendor.status == 'approved',
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator

def vendor_status_check(function):
    """
    Decorator for views that checks the status of the vendor,
    redirecting to the appropriate page based on their status.
    """
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('vendor:vendor_login')
        if not hasattr(request.user, 'vendor'):
            raise PermissionDenied
        vendor = request.user.vendor
        if vendor.status == 'pending':
            return redirect('vendor:application_under_review')
        elif vendor.status == 'rejected':
            return redirect('vendor:application_rejected')
        elif vendor.status == 'approved':
            return function(request, *args, **kwargs)
        else:
            raise PermissionDenied
    return wrap
