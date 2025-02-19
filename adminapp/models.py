from django.db import models
from django.conf import settings

# Create your models here.

class AdminAction(models.Model):
    ACTION_TYPES = (
        ('driver_approval', 'Driver Approval'),
        ('driver_rejection', 'Driver Rejection'),
        ('driver_suspension', 'Driver Suspension'),
        ('document_verification', 'Document Verification'),
    )

    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE)
    action_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.get_action_type_display()} by {self.admin.full_name}"
