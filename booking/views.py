from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from blockchain.driver_verification import DriverBlockchain
from drivers.models import Driver
from .models import Booking
import logging

logger = logging.getLogger(__name__)

@login_required
def book_driver(request, driver_id):
    try:
        # Get driver details
        driver = Driver.objects.get(id=driver_id)
        
        if request.method == 'POST':
            # Create driver data for verification
            driver_data = {
                'license_number': driver.license_number,
                'full_name': f"{driver.user.first_name} {driver.user.last_name}",
                'dob': driver.date_of_birth.strftime('%Y-%m-%d')
            }
            
            # Initialize blockchain verification
            blockchain = DriverBlockchain()
            
            # Verify driver on blockchain
            is_verified = blockchain.verify_driver(str(driver_id), driver_data)
            
            if not is_verified:
                logger.warning(f"Blockchain verification failed for driver {driver_id}")
                messages.error(request, 'Driver verification failed! Cannot proceed with booking.')
                return redirect('booking_error')
            
            # Create booking
            booking = Booking.objects.create(
                user=request.user,
                driver=driver,
                status='pending'
            )
            
            messages.success(request, 'Booking confirmed with blockchain-verified driver!')
            return redirect('booking_success', booking_id=booking.id)
            
        return render(request, 'booking/book_driver.html', {
            'driver': driver
        })
        
    except Driver.DoesNotExist:
        messages.error(request, 'Driver not found!')
        return redirect('booking_error')
    except Exception as e:
        logger.error(f"Booking error: {str(e)}")
        messages.error(request, 'An error occurred during booking. Please try again.')
        return redirect('booking_error')

@login_required
def complete_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        
        if request.method == 'POST':
            rating = int(float(request.POST.get('rating', 0)) * 100)  # Convert to blockchain format
            
            # Update blockchain with booking completion and rating
            blockchain = DriverBlockchain()
            blockchain.contract.functions.updateBookingAndRating(
                str(booking.driver.id),
                rating
            ).transact()
            
            # Update booking status
            booking.status = 'completed'
            booking.rating = rating / 100  # Convert back to decimal
            booking.save()
            
            messages.success(request, 'Booking completed and rating recorded on blockchain!')
            return redirect('booking_history')
            
        return render(request, 'booking/complete_booking.html', {
            'booking': booking
        })
        
    except Booking.DoesNotExist:
        messages.error(request, 'Booking not found!')
        return redirect('booking_error')
    except Exception as e:
        logger.error(f"Booking completion error: {str(e)}")
        messages.error(request, 'An error occurred while completing the booking.')
        return redirect('booking_error') 