from django.core.management.base import BaseCommand
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
from django.conf import settings
from vendor.models import Vehicle

class Command(BaseCommand):
    help = 'Retrains the ML model for price prediction'

    def handle(self, *args, **options):
        self.stdout.write('Starting model retraining...')
        
        # Check if CSV exists, if not export data from database
        csv_path = os.path.join(settings.BASE_DIR, 'vehicle_rental_data.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write('CSV file not found. Exporting data from database...')
            self.export_data_to_csv(csv_path)
        
        # Load the data
        df = pd.read_csv(csv_path)
        self.stdout.write(f"Loaded {len(df)} vehicle records for training")
        
        # Prepare features and target
        X = df[['year', 'mileage', 'seating_capacity', 'transmission', 'air_conditioning', 
                'fuel_efficiency', 'model_year', 'num_features', 'fuel_type', 'vehicle_type', 'brand_tier']]
        y = df['rental_rate']
        
        # Encode categorical variables
        X = pd.get_dummies(X, columns=['transmission', 'fuel_type', 'vehicle_type', 'brand_tier'], drop_first=True)
        
        # Print the feature columns to help with debugging
        self.stdout.write(f"Model will be trained with these features: {X.columns.tolist()}")
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train the model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        # Evaluate the model
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        self.stdout.write(f"Mean Squared Error: {mse}")
        self.stdout.write(f"R-squared Score: {r2}")
        
        # Save the model
        model_path = os.path.join(settings.BASE_DIR, 'trained_rental_price_model.joblib')
        joblib.dump(model, model_path)
        
        self.stdout.write(self.style.SUCCESS(f"Model trained and saved as '{model_path}'"))
        
        # Save the feature columns for reference
        feature_columns = X.columns.tolist()
        with open(os.path.join(settings.BASE_DIR, 'model_features.txt'), 'w') as f:
            f.write('\n'.join(feature_columns))
        
        self.stdout.write(self.style.SUCCESS(f"Feature columns saved to 'model_features.txt'"))
    
    def export_data_to_csv(self, csv_path):
        """Export vehicle data from the database to a CSV file"""
        vehicles = Vehicle.objects.select_related('model', 'model__sub_category', 'model__sub_category__category').all()
        
        data = []
        for vehicle in vehicles:
            try:
                # Map categorical values
                transmission = 'automatic' if vehicle.transmission == 'automatic' else 'manual'
                
                # Determine brand tier based on company name or other logic
                if hasattr(vehicle.model.sub_category, 'company_name'):
                    company = vehicle.model.sub_category.company_name.lower()
                    if company in ['bmw', 'mercedes', 'audi', 'lexus']:
                        brand_tier = 'premium'
                    elif company in ['toyota', 'honda', 'ford', 'hyundai']:
                        brand_tier = 'mid-range'
                    else:
                        brand_tier = 'budget'
                else:
                    brand_tier = 'mid-range'  # Default
                
                # Get vehicle type from category
                if hasattr(vehicle.model.sub_category, 'category'):
                    vehicle_type = vehicle.model.sub_category.category.category_name.lower()
                else:
                    vehicle_type = 'sedan'  # Default
                
                data.append({
                    'year': vehicle.year,
                    'mileage': vehicle.mileage,
                    'seating_capacity': vehicle.seating_capacity,
                    'transmission': transmission,
                    'air_conditioning': vehicle.air_conditioning,
                    'fuel_efficiency': vehicle.fuel_efficiency,
                    'model_year': vehicle.model.model_year,
                    'num_features': vehicle.features.count(),
                    'fuel_type': vehicle.fuel_type,
                    'vehicle_type': vehicle_type,
                    'brand_tier': brand_tier,
                    'rental_rate': float(vehicle.rental_rate) if vehicle.rental_rate else 50.0,
                    'base_rate': 50.0  # Default base rate
                })
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error processing vehicle {vehicle.id}: {str(e)}"))
        
        if data:
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False)
            self.stdout.write(self.style.SUCCESS(f"Exported {len(data)} vehicles to {csv_path}"))
        else:
            self.stdout.write(self.style.WARNING("No vehicle data to export"))
