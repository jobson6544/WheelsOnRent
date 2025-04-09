/**
 * Trip Tracking System
 * This file handles real-time location tracking during trips
 */

class TripTracker {
    constructor(tripId, options = {}) {
        // Trip details
        this.tripId = tripId;
        this.tracking = false;
        this.watchId = null;
        
        // Configuration options with defaults
        this.options = {
            updateInterval: options.updateInterval || 30000, // 30 seconds by default
            updateUrl: options.updateUrl || `/drivers/trips/${tripId}/location/update/`,
            csrfToken: options.csrfToken || this.getCsrfToken(),
            onLocationUpdate: options.onLocationUpdate || function() {},
            onError: options.onError || function(error) { console.error('Trip tracking error:', error); }
        };
        
        // Tracking interval ID
        this.intervalId = null;
    }
    
    /**
     * Start tracking the trip
     */
    start() {
        if (this.tracking) {
            return false; // Already tracking
        }
        
        if (!navigator.geolocation) {
            this.options.onError('Geolocation is not supported by this browser');
            return false;
        }
        
        // Set tracking flag
        this.tracking = true;
        
        // Start watching position with high accuracy
        this.watchId = navigator.geolocation.watchPosition(
            this.handlePositionUpdate.bind(this),
            this.handlePositionError.bind(this),
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 10000
            }
        );
        
        // Set interval to send periodic updates
        this.intervalId = setInterval(() => {
            this.sendCurrentLocation();
        }, this.options.updateInterval);
        
        console.log(`Trip tracking started for trip ${this.tripId}`);
        return true;
    }
    
    /**
     * Stop tracking the trip
     */
    stop() {
        if (!this.tracking) {
            return false; // Not tracking
        }
        
        // Clear the watch and interval
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        
        if (this.intervalId !== null) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        
        // Update tracking flag
        this.tracking = false;
        
        console.log(`Trip tracking stopped for trip ${this.tripId}`);
        return true;
    }
    
    /**
     * Handle position updates from the geolocation API
     */
    handlePositionUpdate(position) {
        const locationData = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            speed: position.coords.speed || 0,
            heading: position.coords.heading || 0,
            timestamp: new Date().toISOString()
        };
        
        // Call the user callback
        this.options.onLocationUpdate(locationData);
        
        // Store current position
        this.currentPosition = locationData;
    }
    
    /**
     * Handle position errors from the geolocation API
     */
    handlePositionError(error) {
        let errorMsg;
        
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMsg = "User denied the request for geolocation";
                break;
            case error.POSITION_UNAVAILABLE:
                errorMsg = "Location information is unavailable";
                break;
            case error.TIMEOUT:
                errorMsg = "The request to get user location timed out";
                break;
            default:
                errorMsg = "An unknown error occurred";
                break;
        }
        
        this.options.onError(errorMsg);
    }
    
    /**
     * Send the current location to the server
     */
    sendCurrentLocation() {
        if (!this.currentPosition) {
            return; // No position to send
        }
        
        const formData = new FormData();
        formData.append('latitude', this.currentPosition.latitude);
        formData.append('longitude', this.currentPosition.longitude);
        
        if (this.currentPosition.accuracy) {
            formData.append('accuracy', this.currentPosition.accuracy);
        }
        
        if (this.currentPosition.speed) {
            formData.append('speed', this.currentPosition.speed);
        }
        
        if (this.currentPosition.heading) {
            formData.append('heading', this.currentPosition.heading);
        }
        
        // Send AJAX request to update location
        fetch(this.options.updateUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': this.options.csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') {
                console.error('Error updating location:', data.message);
            }
        })
        .catch(error => {
            console.error('Failed to send location update:', error);
        });
    }
    
    /**
     * Get the CSRF token from the cookie
     */
    getCsrfToken() {
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
    
    /**
     * Check if tracking is currently active
     */
    isTracking() {
        return this.tracking;
    }
}

// Export the class
window.TripTracker = TripTracker; 