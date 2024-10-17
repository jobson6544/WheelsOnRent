import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

# Number of samples
n_samples = 1000

# Generate data
current_year = datetime.now().year

data = {
    'year': np.random.randint(current_year - 15, current_year + 1, n_samples),
    'mileage': np.zeros(n_samples),
    'seating_capacity': np.random.choice([2, 4, 5, 7, 8], n_samples, p=[0.05, 0.3, 0.4, 0.2, 0.05]),
    'transmission': np.random.choice(['manual', 'automatic'], n_samples, p=[0.6, 0.4]),
    'air_conditioning': np.random.choice([True, False], n_samples, p=[0.9, 0.1]),
    'fuel_efficiency': np.zeros(n_samples),
    'model_year': np.zeros(n_samples),
    'num_features': np.random.randint(1, 11, n_samples),
    'fuel_type': np.random.choice(['petrol', 'diesel', 'electric', 'hybrid', 'cng', 'lpg'], n_samples, p=[0.4, 0.3, 0.05, 0.1, 0.1, 0.05]),
    'vehicle_type': np.random.choice(['sedan', 'suv', 'hatchback', 'luxury', 'van'], n_samples, p=[0.3, 0.25, 0.2, 0.15, 0.1]),
    'brand_tier': np.random.choice(['budget', 'mid-range', 'premium', 'luxury'], n_samples, p=[0.2, 0.4, 0.3, 0.1]),
    'rental_rate': np.zeros(n_samples)
}

df = pd.DataFrame(data)

# Calculate mileage based on year
df['mileage'] = (current_year - df['year']) * np.random.randint(8000, 15000, n_samples) + np.random.randint(0, 5000, n_samples)

# Ensure model_year is not greater than manufacturing year
df['model_year'] = df['year'] - np.random.randint(0, 3, n_samples)
df.loc[df['model_year'] < current_year - 15, 'model_year'] = df['year']

# Calculate fuel efficiency
df.loc[df['fuel_type'] == 'petrol', 'fuel_efficiency'] = np.random.uniform(10, 18, sum(df['fuel_type'] == 'petrol'))
df.loc[df['fuel_type'] == 'diesel', 'fuel_efficiency'] = np.random.uniform(14, 22, sum(df['fuel_type'] == 'diesel'))
df.loc[df['fuel_type'] == 'electric', 'fuel_efficiency'] = np.random.uniform(3, 7, sum(df['fuel_type'] == 'electric'))  # kWh/100km
df.loc[df['fuel_type'] == 'hybrid', 'fuel_efficiency'] = np.random.uniform(18, 25, sum(df['fuel_type'] == 'hybrid'))
df.loc[df['fuel_type'] == 'cng', 'fuel_efficiency'] = np.random.uniform(20, 28, sum(df['fuel_type'] == 'cng'))
df.loc[df['fuel_type'] == 'lpg', 'fuel_efficiency'] = np.random.uniform(8, 12, sum(df['fuel_type'] == 'lpg'))

# Calculate base rental rate
df['base_rate'] = 50  # Base rate for all vehicles

# Adjust rate based on vehicle type
type_multipliers = {'sedan': 1, 'suv': 1.2, 'hatchback': 0.9, 'luxury': 1.5, 'van': 1.3}
df['rental_rate'] = df.apply(lambda row: row['base_rate'] * type_multipliers[row['vehicle_type']], axis=1)

# Adjust rate based on brand tier
tier_multipliers = {'budget': 0.8, 'mid-range': 1, 'premium': 1.3, 'luxury': 1.8}
df['rental_rate'] *= df['brand_tier'].map(tier_multipliers)

# Adjust rate based on year
df['rental_rate'] += (df['year'] - (current_year - 15)) * 2

# Adjust rate based on transmission
df.loc[df['transmission'] == 'automatic', 'rental_rate'] += 10

# Adjust rate based on air conditioning
df.loc[df['air_conditioning'], 'rental_rate'] += 5

# Adjust rate based on seating capacity
df['rental_rate'] += (df['seating_capacity'] - 4) * 5

# Adjust rate based on fuel type
fuel_type_adjustments = {'petrol': 0, 'diesel': 5, 'electric': 15, 'hybrid': 10, 'cng': -5, 'lpg': -5}
df['rental_rate'] += df['fuel_type'].map(fuel_type_adjustments)

# Adjust rate based on number of features
df['rental_rate'] += df['num_features'] * 2

# Add some randomness
df['rental_rate'] += np.random.normal(0, 5, n_samples)

# Round rental rate to nearest integer
df['rental_rate'] = np.round(df['rental_rate']).astype(int)

# Ensure minimum rental rate
df['rental_rate'] = df['rental_rate'].clip(lower=20)

# Save to CSV
df.to_csv('vehicle_rental_data.csv', index=False)

print("Dataset created and saved as 'vehicle_rental_data.csv'")
print(df.describe())

