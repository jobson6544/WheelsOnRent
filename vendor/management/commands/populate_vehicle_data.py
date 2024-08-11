from django.core.management.base import BaseCommand
from vendor.models import VehicleType, VehicleCompany, Model, Features

class Command(BaseCommand):
    help = 'Populates the database with initial vehicle data'

    def handle(self, *args, **kwargs):
        self.populate_vehicle_types()
        self.populate_vehicle_companies()
        self.populate_models()
        self.populate_features()

        self.stdout.write(self.style.SUCCESS('Successfully populated vehicle data'))

    def populate_vehicle_types(self):
        vehicle_types = [
            'Car',
            'Motorcycle',
            'Scooter',
            'Van'
        ]
        for vt in vehicle_types:
            VehicleType.objects.get_or_create(category_name=vt)

    def populate_vehicle_companies(self):
        companies = {
            'Car': ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'Volkswagen'],
            'Motorcycle': ['Harley-Davidson', 'Honda', 'Yamaha', 'Kawasaki', 'Suzuki'],
            'Scooter': ['Vespa', 'Honda', 'Yamaha', 'Piaggio', 'Suzuki'],
            'Van': ['Ford', 'Mercedes-Benz', 'Volkswagen', 'Chevrolet', 'Ram']
        }
        for vehicle_type, company_list in companies.items():
            vt, _ = VehicleType.objects.get_or_create(category_name=vehicle_type)
            for company in company_list:
                VehicleCompany.objects.get_or_create(category=vt, company_name=company)

    def populate_models(self):
        models = {
            'Toyota': ['Corolla', 'Camry', 'RAV4', 'Highlander'],
            'Honda': ['Civic', 'Accord', 'CR-V', 'Pilot'],
            'Ford': ['Mustang', 'Explorer', 'Escape', 'Transit'],
            'Chevrolet': ['Malibu', 'Equinox', 'Traverse', 'Express'],
            'Volkswagen': ['Golf', 'Passat', 'Tiguan', 'Atlas'],
            'Harley-Davidson': ['Sportster', 'Softail', 'Touring', 'Street'],
            'Yamaha': ['YZF-R1', 'MT-09', 'YZF-R6', 'TMAX'],
            'Kawasaki': ['Ninja', 'Z900', 'Versys', 'Vulcan'],
            'Suzuki': ['GSX-R1000', 'V-Strom', 'Hayabusa', 'SV650'],
            'Vespa': ['Primavera', 'Sprint', 'GTS', 'Elettrica'],
            'Piaggio': ['Liberty', 'Beverly', 'MP3', 'Medley'],
            'Mercedes-Benz': ['Sprinter', 'Metris', 'Vito', 'eVito'],
            'Ram': ['ProMaster', 'ProMaster City']
        }
        for company, model_list in models.items():
            vc = VehicleCompany.objects.filter(company_name=company).first()
            if vc:
                for model in model_list:
                    Model.objects.get_or_create(
                        sub_category=vc,
                        model_name=model,
                        model_year=2023  # Using a fixed year for simplicity
                    )

    def populate_features(self):
        features = [
            'Air Conditioning',
            'GPS Navigation',
            'Bluetooth',
            'Backup Camera',
            'Cruise Control',
            'Leather Seats',
            'Sunroof',
            'Heated Seats',
            'Keyless Entry',
            'Apple CarPlay/Android Auto'
        ]
        for feature in features:
            Features.objects.get_or_create(feature_name=feature)