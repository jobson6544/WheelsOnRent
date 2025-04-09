/**
 * WheelsOnRent Driver GPS Tracking Module
 * This module handles GPS tracking functionality for driver trips
 */

const TripTracker = {
    watchId: null,
    trackingInterval: null,
    isTracking: false,
    position: null,
    csrfToken: null,
    
    /**
     * Initialize the trip tracker
     * @param {string} csrfToken - CSRF token for making POST requests
     */
    init: function(csrfToken) {
        this.csrfToken = csrfToken;
        
        // Check if geolocation is available
        if (!navigator.geolocation) {
            console.error('Geolocation is not supported by this browser');
            return false;
        }
        
        return true;
    },
    
    /**
     * Start GPS tracking
     * @param {string} tripId - ID of the trip being tracked
     * @param {number} interval - Interval in milliseconds between location updates
     */
    startTracking: function(tripId, interval = 30000) {
        if (this.isTracking) {
            console.warn('Tracking is already active');
            return;
        }
        
        if (!navigator.geolocation) {
            console.error('Geolocation is not supported by this browser');
            return;
        }
        
        // Get high accuracy initial position
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.position = position;
                this.sendLocationUpdate(tripId, position);
                
                // Start tracking at regular intervals
                this.trackingInterval = setInterval(() => {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            this.position = pos;
                            this.sendLocationUpdate(tripId, pos);
                        },
                        (error) => {
                            console.error('Error getting position:', error);
                        },
                        {
                            enableHighAccuracy: true,
                            timeout: 10000,
                            maximumAge: 0
                        }
                    );
                }, interval);
                
                this.isTracking = true;
                
                // Use the watchPosition API as a backup
                this.watchId = navigator.geolocation.watchPosition(
                    (pos) => {
                        // Only update if significant movement is detected
                        if (this.hasSignificantMovement(this.position, pos)) {
                            this.position = pos;
                            this.sendLocationUpdate(tripId, pos);
                        }
                    },
                    (error) => {
                        console.error('Error watching position:', error);
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    }
                );
                
                console.log('GPS tracking started');
            },
            (error) => {
                console.error('Error starting tracking:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    },
    
    /**
     * Stop GPS tracking
     */
    stopTracking: function() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        
        if (this.trackingInterval !== null) {
            clearInterval(this.trackingInterval);
            this.trackingInterval = null;
        }
        
        this.isTracking = false;
        console.log('GPS tracking stopped');
    },
    
    /**
     * Send location update to server
     * @param {string} tripId - ID of the trip being tracked
     * @param {GeolocationPosition} position - Current position
     */
    sendLocationUpdate: function(tripId, position) {
        const { latitude, longitude, accuracy, speed, heading } = position.coords;
        
        fetch('/drivers/location/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': this.csrfToken,
            },
            body: new URLSearchParams({
                'latitude': latitude,
                'longitude': longitude,
                'accuracy': accuracy || 0,
                'speed': speed || 0,
                'heading': heading || 0,
                'trip_id': tripId
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Location update sent:', data);
            
            // Dispatch event that location was updated
            const event = new CustomEvent('locationUpdated', { 
                detail: {
                    position: position,
                    response: data
                } 
            });
            document.dispatchEvent(event);
        })
        .catch(error => {
            console.error('Error sending location update:', error);
        });
    },
    
    /**
     * Check if there's been significant movement between positions
     * @param {GeolocationPosition} oldPos - Previous position
     * @param {GeolocationPosition} newPos - New position
     * @returns {boolean} True if movement is significant
     */
    hasSignificantMovement: function(oldPos, newPos) {
        if (!oldPos) return true;
        
        // Calculate distance between points (simple approximation)
        const distance = this.calculateDistance(
            oldPos.coords.latitude, 
            oldPos.coords.longitude,
            newPos.coords.latitude,
            newPos.coords.longitude
        );
        
        // Consider movement significant if more than 10 meters
        return distance > 10;
    },
    
    /**
     * Calculate distance between two coordinates in meters
     */
    calculateDistance: function(lat1, lon1, lat2, lon2) {
        const R = 6371e3; // Earth radius in meters
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lon2 - lon1) * Math.PI / 180;
        
        const a = 
            Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
        
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        return R * c; // Distance in meters
    },
    
    /**
     * Get current position coordinates
     * @returns {Promise} Promise resolving to position
     */
    getCurrentPosition: function() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve(position);
                },
                (error) => {
                    reject(error);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }
};

// Export the module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TripTracker;
} 