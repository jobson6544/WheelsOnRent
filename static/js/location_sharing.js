/**
 * Location Sharing Button Implementation
 * 
 * This script creates a location sharing button that can be added to any page.
 * It requires the global WheelsOnRentLocationServices to be available.
 * 
 * Usage:
 * 1. Include this script on your page after base.html
 * 2. Call createShareLocationButton with a container element ID and booking ID
 */

function createShareLocationButton(containerId, bookingId) {
    // Make sure the container exists
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container element with ID '${containerId}' not found`);
        return;
    }
    
    // Create the button
    const button = document.createElement('button');
    button.className = 'btn btn-primary share-location-btn';
    button.innerHTML = '<i class="fas fa-map-marker-alt"></i> Share My Location';
    button.setAttribute('type', 'button');
    button.setAttribute('aria-label', 'Share my location');
    
    // Add click event
    button.addEventListener('click', function() {
        // Check if global location services are available
        if (!window.WheelsOnRentLocationServices) {
            console.error('WheelsOnRentLocationServices not available');
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Location services are not available. Please try again later.',
                confirmButtonColor: '#1e3c72'
            });
            return;
        }
        
        // Disable button and show loading state
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Getting location...';
        
        // Request location permission first
        window.WheelsOnRentLocationServices.requestPermission(
            // Success callback - we have coordinates
            function(coords) {
                // Send to server using form submission with POST (more reliable than fetch)
                const url = `/mainapp/rental/${bookingId}/share-location/`;
                
                // Create a hidden form and submit it
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = url;
                form.style.display = 'none';
                
                // Add CSRF token
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = getCsrfToken();
                form.appendChild(csrfInput);
                
                // Add coordinates
                const latInput = document.createElement('input');
                latInput.type = 'hidden';
                latInput.name = 'latitude';
                latInput.value = coords.latitude;
                form.appendChild(latInput);
                
                const lngInput = document.createElement('input');
                lngInput.type = 'hidden';
                lngInput.name = 'longitude';
                lngInput.value = coords.longitude;
                form.appendChild(lngInput);
                
                try {
                    // Add form to document and submit - don't show the intermediate popup
                    document.body.appendChild(form);
                    form.submit();
                    
                    // We don't need to reset the button or close the popup since we're redirecting
                } catch (err) {
                    console.error("Error submitting form:", err);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Failed to share location. Please try again.',
                        confirmButtonColor: '#1e3c72'
                    });
                    button.disabled = false;
                    button.innerHTML = '<i class="fas fa-map-marker-alt"></i> Share My Location';
                }
            },
            // Error callback - permission denied or error
            function(error) {
                console.error("Location sharing error:", error);
                
                // Show error message
                Swal.fire({
                    icon: 'error',
                    title: 'Location Error',
                    text: 'Unable to share your location. Please check your browser permissions and try again.',
                    confirmButtonColor: '#1e3c72'
                });
                
                // Reset button
                button.disabled = false;
                button.innerHTML = '<i class="fas fa-map-marker-alt"></i> Share My Location';
            }
        );
    });
    
    // Add the button to the container
    container.appendChild(button);
    
    return button;
}

// Get CSRF token from cookies
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Auto-initialize any buttons with data attributes
document.addEventListener('DOMContentLoaded', function() {
    const buttons = document.querySelectorAll('[data-share-location-booking]');
    buttons.forEach(container => {
        const bookingId = container.getAttribute('data-share-location-booking');
        if (bookingId) {
            createShareLocationButton(container.id, bookingId);
        }
    });
}); 