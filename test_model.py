import pandas as pd
import joblib
import os
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

# Load the model
model_path = os.path.join(BASE_DIR, 'trained_rental_price_model.joblib')
model = joblib.load(model_path)

print("Model loaded successfully!")

# Create a sample vehicle for prediction
sample_vehicle = pd.DataFrame({
    'year': [2020],
    'mileage': [50000],
    'seating_capacity': [5],
    'air_conditioning': [1.0],
    'fuel_efficiency': [15.0],
    'model_year': [2019],
    'num_features': [8],
    'transmission_manual': [0.0],  # automatic
    'fuel_type_diesel': [0.0],
    'fuel_type_electric': [0.0],
    'fuel_type_hybrid': [0.0],
    'fuel_type_lpg': [0.0],
    'fuel_type_petrol': [1.0],  # petrol
    'vehicle_type_luxury': [0.0],
    'vehicle_type_sedan': [1.0],  # sedan
    'vehicle_type_suv': [0.0],
    'vehicle_type_van': [0.0],
    'brand_tier_luxury': [0.0],
    'brand_tier_mid-range': [1.0],  # mid-range
    'brand_tier_premium': [0.0]
})

# Make prediction
predicted_price = model.predict(sample_vehicle)[0]
print(f"Predicted rental price: ${predicted_price:.2f}")

# Try another vehicle with different features
premium_suv = pd.DataFrame({
    'year': [2022],
    'mileage': [20000],
    'seating_capacity': [7],
    'air_conditioning': [1.0],
    'fuel_efficiency': [12.0],
    'model_year': [2021],
    'num_features': [10],
    'transmission_manual': [0.0],  # automatic
    'fuel_type_diesel': [1.0],  # diesel
    'fuel_type_electric': [0.0],
    'fuel_type_hybrid': [0.0],
    'fuel_type_lpg': [0.0],
    'fuel_type_petrol': [0.0],
    'vehicle_type_luxury': [0.0],
    'vehicle_type_sedan': [0.0],
    'vehicle_type_suv': [1.0],  # SUV
    'vehicle_type_van': [0.0],
    'brand_tier_luxury': [0.0],
    'brand_tier_mid-range': [0.0],
    'brand_tier_premium': [1.0]  # premium
})

# Make prediction
premium_price = model.predict(premium_suv)[0]
print(f"Predicted rental price for premium SUV: ${premium_price:.2f}")

# Check feature importance
feature_importance = pd.DataFrame({
    'Feature': sample_vehicle.columns,
    'Importance': model.feature_importances_
}).sort_values('Importance', ascending=False)

print("\nFeature Importance:")
print(feature_importance.head(10))  # Show top 10 important features 