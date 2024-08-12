from django.contrib import admin
from .models import Vendor, Vehicle

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'status', 'city', 'state')
    list_filter = ('status', 'city', 'state')
    search_fields = ('business_name', 'user__username', 'user__email')
# Register your models here.

admin.site.register(Vehicle)