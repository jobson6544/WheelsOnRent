from django.shortcuts import redirect
from .models import UserProfile, User
import logging

logger = logging.getLogger(__name__)

def check_first_login(backend, user, response, *args, **kwargs):
    if user.is_first_login:
        user.is_first_login = False
        user.save()
        return redirect('mainapp:complete_profile')
    return None  # Continue with the pipeline if profile is complete

def create_user(strategy, details, backend, user=None, *args, **kwargs):
    logger.info(f"Starting create_user pipeline with details: {details}")
    
    if user:
        logger.info(f"User already exists in pipeline: {user.email}")
        if user.auth_method != 'google':
            user.auth_method = 'google'
            user.save()
        return {'is_new': False, 'user': user}

    email = details.get('email')
    if not email:
        logger.error("No email found in details")
        return None

    # Try to get existing user by email
    try:
        existing_user = User.objects.get(email=email)
        logger.info(f"Found existing user by email: {email}")
        
        # Update existing user's Google auth method if needed
        if existing_user.auth_method != 'google':
            existing_user.auth_method = 'google'
            existing_user.save()
        
        return {
            'is_new': False,
            'user': existing_user
        }
        
    except User.DoesNotExist:
        logger.info(f"Creating new user with email: {email}")
        username = email  # Use email as username
        
        # Create new user
        user = strategy.create_user(
            username=username,
            email=email,
            password=None,  # No password for Google auth
            full_name=details.get('fullname', ''),
            first_name=details.get('first_name', ''),
            last_name=details.get('last_name', ''),
            auth_method='google',
            role='user',
            is_first_login=True,
            is_email_verified=True,
            is_active=True
        )
        
        logger.info(f"Successfully created new user: {user.email}")
        return {
            'is_new': True,
            'user': user
        }