from django.contrib import admin
from .models import Vendor, Vehicle

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_id', 'business_name', 'full_address', 'contact_number', 'status')
    list_filter = ('status',)
    search_fields = ('business_name', 'full_address', 'contact_number')
    readonly_fields = ('latitude', 'longitude')

    fieldsets = (
        (None, {
            'fields': ('user', 'business_name', 'full_address', 'contact_number', 'status')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',),
        }),
    )
# Register your models here.

admin.site.register(Vehicle)

class VehicleAdmin(admin.ModelAdmin):
    list_display = ['model', 'rental_rate', 'get_suggested_price_display']

    def get_suggested_price_display(self, obj):
        return f"${obj.get_suggested_price():.2f}"
    get_suggested_price_display.short_description = 'Suggested Price'

# Check if Vehicle is already registered
if not admin.site.is_registered(Vehicle):
    admin.site.register(Vehicle, VehicleAdmin)