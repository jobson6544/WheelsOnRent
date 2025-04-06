from vendor.models import Vendor
from mainapp.models import Booking, AccidentReport
from django.db.models import Count

def vendor_processor(request):
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'vendor'):
        try:
            vendor = request.user.vendor
            
            # Get count of pending bookings
            pending_bookings = Booking.objects.filter(
                vehicle__vendor=vendor,
                status='pending'
            ).count()
            
            context['pending_bookings_count'] = pending_bookings
            
            # Get count of emergency accident reports
            emergency_reports = AccidentReport.objects.filter(
                booking__vehicle__vendor=vendor,
                is_emergency=True,
                status='reported'
            ).count()
            
            context['emergency_reports_count'] = emergency_reports
            
        except Vendor.DoesNotExist:
            pass
    
    return context 