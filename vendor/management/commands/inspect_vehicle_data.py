from django.core.management.base import BaseCommand
from vendor.models import VehicleType, VehicleCompany, Model

class Command(BaseCommand):
    help = 'Inspect vehicle data in the database'

    def handle(self, *args, **options):
        self.stdout.write("Vehicle Types:")
        for vt in VehicleType.objects.all():
            self.stdout.write(f"  - {vt.category_id}: {vt.category_name}")

        self.stdout.write("\nVehicle Companies:")
        for vc in VehicleCompany.objects.all():
            self.stdout.write(f"  - {vc.sub_category_id}: {vc.company_name} (Type: {vc.category.category_name})")

        self.stdout.write("\nModels:")
        for model in Model.objects.all():
            self.stdout.write(f"  - {model.model_id}: {model.model_name} "
                              f"(Year: {model.model_year}, "
                              f"Company: {model.sub_category.company_name}, "
                              f"Type: {model.sub_category.category.category_name})")
