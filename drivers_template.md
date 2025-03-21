# WheelsOnRent - Drivers Module Documentation

## Models

### DriverAuth
A model that handles driver authentication.

**Fields:**
- email (unique)
- password (hashed)
- is_active
- is_email_verified
- email_verification_token
- password_reset_token
- password_reset_token_created_at
- last_login
- created_at
- session_token
- session_expires

**Methods:**
- set_password(raw_password)
- check_password(raw_password)
- generate_verification_token()
- generate_password_reset_token()
- create_session()
- is_session_valid(token)
- __str__()

### Driver
The main driver model with personal and professional information.

**Fields:**
- auth (OneToOneField to DriverAuth)
- full_name
- phone_number
- address
- city
- license_number (unique)
- driving_experience
- driving_skill (choices: car, bike, both)
- status (choices: pending_approval, approved, rejected, suspended)
- profile_photo
- approved_at
- approved_by
- availability_status (choices: available, unavailable)

**Methods:**
- __str__()
- send_approval_email()
- send_rejection_email(reason='')

### DriverApplicationLog
Tracks changes to driver application status.

**Fields:**
- driver (ForeignKey to Driver)
- admin (ForeignKey to User)
- action
- notes
- timestamp

**Methods:**
- __str__()

### DriverBooking
Handles bookings made for drivers.

**Fields:**
- driver (ForeignKey to Driver)
- user (ForeignKey to User)
- start_date
- end_date
- amount
- status (choices: pending, confirmed, cancelled, completed)
- payment_status (choices: pending, paid, failed, refunded)
- created_at
- updated_at

**Methods:**
- __str__()
- send_confirmation_email()
- can_start_trip()
- can_end_trip()
- trip()

### DriverReview
Stores reviews for drivers.

**Fields:**
- driver_booking (ForeignKey to DriverBooking)
- rating (1-5)
- comment
- created_at
- created_by (ForeignKey to User)

### DriverVehicleAssignment
Links drivers to specific vehicles.

**Fields:**
- driver (ForeignKey to Driver)
- vehicle (ForeignKey to Vehicle)
- is_active
- assigned_date
- end_date
- assignment_notes

### DriverDocument
Stores documents associated with drivers.

**Fields:**
- driver (ForeignKey to Driver)
- document_type (choices: license, identity, address)
- document
- uploaded_at
- is_verified
- verified_at
- verified_by

**Methods:**
- __str__()

### DriverSchedule
Manages driver schedules and availability.

**Fields:**
- driver (ForeignKey to Driver)
- date
- start_time
- end_time
- is_available
- notes

### DriverTrip
Records trip details for drivers.

**Fields:**
- driver (ForeignKey to Driver)
- booking (ForeignKey to Booking)
- status (choices: assigned, started, completed, cancelled)
- start_time
- end_time
- start_location
- end_location
- distance_covered
- customer_rating
- customer_feedback

**Methods:**
- __str__()

## Forms

### DriverRegistrationForm
Form for driver registration.

**Fields:**
- email
- password
- confirm_password
- full_name
- phone_number
- license_number
- driving_experience
- driving_skill
- address
- city
- profile_photo
- license_document

**Methods:**
- clean_email()
- clean()
- save()

### DriverLoginForm
Form for driver login.

**Fields:**
- email
- password

### DriverUpdateForm
Form for updating driver information.

**Fields:**
- full_name
- phone_number
- address
- city
- profile_photo

### DriverDocumentForm
Form for uploading driver documents.

**Fields:**
- document_type
- document

**Methods:**
- __init__()
- clean_document()

## Views

### Authentication Functions
- driver_login_required(view_func) - Custom decorator for driver authentication
- driver_login(request) - Login function for drivers
- driver_logout(request) - Logout function for drivers
- approval_status(request) - Shows driver approval status
- register_driver(request) - Handles driver registration

### Dashboard and Profile Functions
- driver_dashboard(request) - Driver's main dashboard
- driver_profile(request) - Displays/updates driver profile
- driver_settings(request) - Driver settings
- driver_support(request) - Support page for drivers
- update_settings(request) - Updates driver settings
- update_privacy(request) - Updates privacy settings
- update_account(request) - Updates account information
- change_password(request) - Changes driver password

### Trip Management Functions
- driver_trips(request) - Lists all driver trips
- active_trips(request) - Shows active trips
- completed_trips(request) - Shows completed trips
- start_trip(request, booking_id) - Starts a trip
- end_trip(request, booking_id) - Ends a trip

### Earnings and Financial Functions
- driver_earnings(request) - Shows driver earnings
- earnings_history(request) - Shows earning history

### Document Management Functions
- documents(request) - Manages driver documents

### Status and Update Functions
- update_status(request) - Updates driver availability status

### Booking-related Functions
- book_driver(request, driver_id) - Books a driver
- check_driver_availability(request, driver_id) - Checks if driver is available
- driver_booking_success(request) - Booking success page
- driver_booking_cancel(request) - Cancels a booking
- driver_booking_list(request) - Lists driver bookings

## URLs

- /login/ - Driver login page
- /register/ - Driver registration page
- /logout/ - Driver logout
- /dashboard/ - Driver dashboard
- /profile/ - Driver profile
- /settings/ - Driver settings
- /support/ - Driver support
- /trips/ - Driver trips list
- /trips/active/ - Active trips
- /trips/completed/ - Completed trips
- /earnings/ - Driver earnings
- /earnings/history/ - Earnings history
- /documents/ - Driver documents
- /approval-status/ - Driver approval status
- /update-status/ - Update driver status
- /change-password/ - Change password
- /settings/update/ - Update settings
- /settings/privacy/update/ - Update privacy settings
- /settings/account/update/ - Update account settings
- /book/<driver_id>/ - Book a driver
- /booking/success/ - Booking success page
- /booking/cancel/ - Booking cancellation page
- /booking/list/ - Bookings list
- /trip/<booking_id>/start/ - Start a trip
- /trip/<booking_id>/end/ - End a trip
- /check-availability/<driver_id>/ - Check driver availability 