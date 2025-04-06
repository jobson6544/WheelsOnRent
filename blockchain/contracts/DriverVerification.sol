// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract DriverVerification {
    struct Driver {
        string driverHash;
        uint256 timestamp;
        bool isVerified;
        uint256 totalBookings;
        uint256 rating;  // Average rating * 100 (to handle decimals)
    }
    
    mapping(string => Driver) public drivers;
    address public owner;
    uint256 public totalDrivers;
    
    event DriverRegistered(string indexed driverId, string driverHash, uint256 timestamp);
    event DriverVerified(string indexed driverId, bool status);
    event BookingCompleted(string indexed driverId, uint256 rating);
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can perform this action");
        _;
    }
    
    constructor() {
        owner = msg.sender;
        totalDrivers = 0;
    }
    
    function registerDriver(string memory driverId, string memory driverHash) 
        public 
        onlyOwner 
        returns (bool)
    {
        require(drivers[driverId].timestamp == 0, "Driver already registered");
        
        drivers[driverId] = Driver({
            driverHash: driverHash,
            timestamp: block.timestamp,
            isVerified: true,
            totalBookings: 0,
            rating: 0
        });
        
        totalDrivers++;
        
        emit DriverRegistered(driverId, driverHash, block.timestamp);
        return true;
    }
    
    function verifyDriver(string memory driverId, string memory driverHash) 
        public 
        view 
        returns (bool)
    {
        Driver memory driver = drivers[driverId];
        if (driver.timestamp == 0) return false;
        
        bool isValid = keccak256(abi.encodePacked(driver.driverHash)) == 
                      keccak256(abi.encodePacked(driverHash));
                      
        return isValid && driver.isVerified;
    }
    
    function updateBookingAndRating(string memory driverId, uint256 rating) 
        public 
        onlyOwner 
        returns (bool)
    {
        require(rating >= 0 && rating <= 500, "Rating must be between 0 and 5.00");
        require(drivers[driverId].timestamp > 0, "Driver not registered");
        
        Driver storage driver = drivers[driverId];
        
        // Update total bookings
        driver.totalBookings++;
        
        // Update average rating
        if (driver.rating == 0) {
            driver.rating = rating;
        } else {
            driver.rating = ((driver.rating * (driver.totalBookings - 1)) + rating) / driver.totalBookings;
        }
        
        emit BookingCompleted(driverId, rating);
        return true;
    }
    
    function getDriverDetails(string memory driverId) 
        public 
        view 
        returns (
            uint256 timestamp,
            bool isVerified,
            uint256 totalBookings,
            uint256 rating
        )
    {
        Driver memory driver = drivers[driverId];
        return (
            driver.timestamp,
            driver.isVerified,
            driver.totalBookings,
            driver.rating
        );
    }
    
    function suspendDriver(string memory driverId) 
        public 
        onlyOwner 
        returns (bool)
    {
        require(drivers[driverId].timestamp > 0, "Driver not registered");
        drivers[driverId].isVerified = false;
        emit DriverVerified(driverId, false);
        return true;
    }
    
    function reactivateDriver(string memory driverId) 
        public 
        onlyOwner 
        returns (bool)
    {
        require(drivers[driverId].timestamp > 0, "Driver not registered");
        drivers[driverId].isVerified = true;
        emit DriverVerified(driverId, true);
        return true;
    }
} 