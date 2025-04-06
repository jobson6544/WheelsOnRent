from django.core.management.base import BaseCommand
from drivers.models import Driver
from blockchain.driver_verification import DriverBlockchain
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Register existing drivers on the blockchain'

    def handle(self, *args, **kwargs):
        blockchain = DriverBlockchain()
        drivers = Driver.objects.all()
        
        self.stdout.write('Starting driver registration on blockchain...')
        
        success_count = 0
        error_count = 0
        
        for driver in drivers:
            try:
                # Prepare driver data using the correct model structure
                driver_data = {
                    'license_number': driver.license_number,
                    'full_name': driver.full_name,
                    'dob': driver.created_at.strftime('%Y-%m-%d') if hasattr(driver, 'created_at') else '1900-01-01'
                }
                
                # Register driver
                receipt = blockchain.register_driver(str(driver.id), driver_data)
                
                if receipt:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully registered driver {driver.id} ({driver.full_name}) on blockchain'
                    ))
                else:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'Failed to register driver {driver.id} ({driver.full_name})'
                    ))
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error registering driver {driver.id}: {str(e)}")
                self.stdout.write(self.style.ERROR(
                    f'Error registering driver {driver.id}: {str(e)}'
                ))
        
        self.stdout.write('\nRegistration complete!')
        self.stdout.write(f'Successfully registered: {success_count} drivers')
        self.stdout.write(f'Failed to register: {error_count} drivers') 