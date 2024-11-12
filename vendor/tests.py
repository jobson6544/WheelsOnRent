from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Vendor, Vehicle, VehicleType, VehicleCompany, Model, Registration
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

User = get_user_model()

class VendorAuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.vendor_login_url = reverse('vendor:vendor_login')
        self.vendor_register_url = reverse('vendor:register_user')
        
        # Create vendor user
        self.vendor_data = {
            'email': 'vendor@example.com',
            'username': 'vendor',
            'password': 'testpass123',
            'role': 'vendor'
        }

    def test_vendor_registration(self):
        """Test vendor registration process"""
        response = self.client.post(self.vendor_register_url, self.vendor_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email=self.vendor_data['email']).exists())

    def test_vendor_login(self):
        """Test vendor login process"""
        user = User.objects.create_user(
            email='vendor@example.com',
            username='vendor',
            password='testpass123',
            role='vendor'
        )
        Vendor.objects.create(
            user=user,
            business_name='Test Vendor',
            contact_number='1234567890',
            status='approved'
        )
        
        response = self.client.post(self.vendor_login_url, {
            'email': 'vendor@example.com',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

class VehicleManagementTestCase(TestCase):
    @patch('vendor.models.googlemaps.Client')
    def setUp(self, mock_gmaps):
        self.client = Client()
        
        # Mock geocoding
        mock_gmaps.return_value.geocode.return_value = [{
            'geometry': {
                'location': {
                    'lat': 10.0,
                    'lng': 20.0
                }
            }
        }]
        
        # Create vendor user and login
        self.vendor_user = User.objects.create_user(
            email='vendor@example.com',
            username='vendor',
            password='testpass123',
            role='vendor'
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            business_name='Test Vendor',
            contact_number='1234567890',
            status='approved',
            full_address='Test Address'
        )
        self.client.login(username='vendor@example.com', password='testpass123')
        
        # Create vehicle related objects
        self.vehicle_type = VehicleType.objects.create(category_name='Car')
        self.company = VehicleCompany.objects.create(
            category=self.vehicle_type,
            company_name='Test Company'
        )
        self.model = Model.objects.create(
            sub_category=self.company,
            model_name='Test Model',
            model_year=2023
        )
        self.registration = Registration.objects.create(
            registration_number='KL01AB1234',
            registration_date=timezone.now().date(),
            registration_end_date=timezone.now().date() + timedelta(days=365)
        )

    def test_add_vehicle(self):
        """Test adding a new vehicle"""
        response = self.client.post(reverse('vendor:add_vehicle'), {
            'model': self.model.id,
            'registration': self.registration.id,
            'rental_rate': '100.00',
            'fuel_type': 'petrol',
            'status': 1
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Vehicle.objects.filter(vendor=self.vendor).exists())

    def test_edit_vehicle(self):
        """Test editing an existing vehicle"""
        vehicle = Vehicle.objects.create(
            vendor=self.vendor,
            model=self.model,
            registration=self.registration,
            rental_rate=Decimal('100.00'),
            fuel_type='petrol',
            status=1
        )
        
        response = self.client.post(
            reverse('vendor:edit_vehicle', args=[vehicle.id]),
            {
                'rental_rate': '150.00',
                'status': 2
            }
        )
        
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.rental_rate, Decimal('150.00'))
        self.assertEqual(vehicle.status, 2)
