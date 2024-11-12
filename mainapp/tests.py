from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.conf import settings
from django.contrib import messages
from .models import UserProfile, Booking, Feedback
from vendor.models import Vehicle
from django.utils import timezone
from unittest.mock import patch
from decimal import Decimal
import re
import sys

User = get_user_model()

class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('user_register')
        self.login_url = reverse('user_login')
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'role': 'user',
            'full_name': 'Test User'  # Add if required by your form
        }

    def print_test_result(self, test_name, passed=True):
        """Helper method to print test results"""
        if passed:
            print(f"\033[92m✓ Test Passed: {test_name}\033[0m")  # Green color
        else:
            print(f"\033[91m✗ Test Failed: {test_name}\033[0m")  # Red color
        sys.stdout.flush()  # Ensure immediate output

    @patch('django.contrib.staticfiles.storage.StaticFilesStorage.exists')
    def test_user_registration_and_verification(self, mock_exists):
        """Test user registration and email verification process"""
        mock_exists.return_value = True
        
        # 1. Register new user
        response = self.client.post(self.register_url, self.user_data, follow=True)
        # Using follow=True to follow the redirect
        
        # Check that registration was successful
        self.assertRedirects(response, reverse('user_login'))
        
        # 2. Check that the user was created
        user = User.objects.get(email=self.user_data['email'])
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.email_verification_token)
        
        # 3. Check verification email
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Activate your account')
        self.assertEqual(email.to[0], self.user_data['email'])
        
        # 4. Extract verification token from email
        email_body = email.body
        token_match = re.search(r'verify-email/([^/\s]+)', email_body)
        self.assertIsNotNone(token_match, "Verification token not found in email")
        verification_token = token_match.group(1)
        
        # 5. Verify email
        verify_url = reverse('verify_email', args=[verification_token])
        response = self.client.get(verify_url, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # 6. Check user is verified
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertTrue(user.is_active)

    @patch('django.contrib.staticfiles.storage.StaticFilesStorage.exists')
    def test_invalid_login(self, mock_exists):
        """Test login with invalid credentials"""
        mock_exists.return_value = True
        
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, 200)  # Stays on login page
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertContains(response, "Invalid email or password")  # Assuming this error message

    @patch('django.contrib.staticfiles.storage.StaticFilesStorage.exists')
    def test_unverified_user_login(self, mock_exists):
        """Test login attempt with unverified email"""
        mock_exists.return_value = True
        
        # Create unverified user
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            is_email_verified=False,
            is_active=False,
            role='user'
        )
        
        response = self.client.post(
            self.login_url, 
            {
                'email': 'test@example.com',
                'password': 'testpass123'
            },
            follow=True
        )
        
        # Check for message in response
        messages_list = list(response.context['messages'])
        self.assertTrue(any(message.message == "Please verify your email first" 
                          for message in messages_list))

    @patch('django.contrib.staticfiles.storage.StaticFilesStorage.exists')
    def test_successful_login(self, mock_exists):
        """Test successful login with verified email"""
        try:
            mock_exists.return_value = True
            
            # Create verified user
            user = User.objects.create_user(
                email='test@example.com',
                username='testuser',
                password='testpass123',
                is_email_verified=True,
                is_active=True,
                role='user'
            )
            
            response = self.client.post(self.login_url, {
                'email': 'test@example.com',
                'password': 'testpass123'
            })
            
            self.assertEqual(response.status_code, 302)
            self.assertTrue('_auth_user_id' in self.client.session)
            self.print_test_result("Successful Login Test")
        except AssertionError as e:
            self.print_test_result("Successful Login Test", passed=False)
            raise e

    def test_logout(self):
        """Test user logout"""
        try:
            # Create and login user first
            user = User.objects.create_user(
                email='test@example.com',
                username='testuser',
                password='testpass123',
                is_email_verified=True,
                is_active=True,
                role='user'
            )
            self.client.login(email='test@example.com', password='testpass123')
            
            # Test logout
            response = self.client.get(reverse('logout'))
            self.assertEqual(response.status_code, 302)  # Redirect after logout
            self.assertFalse('_auth_user_id' in self.client.session)
            self.print_test_result("Logout Test")
        except AssertionError as e:
            self.print_test_result("Logout Test", passed=False)
            raise e

class BookingTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            is_email_verified=True,
            is_active=True,
            role='user'
        )
        self.client.login(username='test@example.com', password='testpass123')

    def test_booking_list(self):
        """Test user bookings list view"""
        response = self.client.get(reverse('user_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user_bookings.html')

    def test_booking_detail(self):
        """Test booking detail view"""
        # Create a booking first
        booking = Booking.objects.create(
            user=self.user,
            # Add other required fields based on your Booking model
        )
        
        response = self.client.get(reverse('booking_detail', args=[booking.booking_id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking_detail.html')

class ProfileTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            is_email_verified=True,
            is_active=True,
            role='user'
        )
        self.client.login(username='test@example.com', password='testpass123')

    def test_profile_view(self):
        """Test profile view"""
        response = self.client.get(reverse('profile_view'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile_view.html')

    def test_edit_profile(self):
        """Test profile editing"""
        UserProfile.objects.create(user=self.user)
        
        response = self.client.post(reverse('edit_profile'), {
            'full_name': 'Test User',
            'phone_number': '1234567890',
            'address': 'Test Address'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after successful edit
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.phone_number, '1234567890')

class PasswordResetTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            is_email_verified=True,
            is_active=True,
            role='user'
        )

    def test_forgot_password(self):
        """Test forgot password functionality"""
        response = self.client.post(reverse('forgot_password'), {
            'email': 'test@example.com'
        })
        
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue('OTP' in mail.outbox[0].body)

    def test_password_reset_verify(self):
        """Test password reset verification"""
        # Generate reset token
        token = self.user.generate_password_reset_token()
        
        response = self.client.post(reverse('password_reset_verify'), {
            'email': 'test@example.com',
            'token': token,
            'new_password': 'newpass123'
        })
        
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(
            self.client.login(username='test@example.com', password='newpass123')
        )

class VendorBenefitsTestCase(TestCase):
    def test_profit_calculation(self):
        """Test vendor benefits profit calculation"""
        response = self.client.post(reverse('vendor_benefits'), {
            'rental_days': 5,
            'rental_price': 100
        })
        
        data = response.json()
        self.assertEqual(len(data['total_prices']), 5)
        self.assertEqual(data['total_prices'][0], 100)  # First day price
        self.assertEqual(data['wheels_on_rent_fees'][0], 10)  # 10% fee
        self.assertEqual(data['vendor_profits'][0], 90)  # Profit after fee
