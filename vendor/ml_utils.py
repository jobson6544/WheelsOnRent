import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib
from .models import Vehicle

def train_model():
    vehicles = Vehicle.objects.all()

    if not vehicles.exists():
        print("No vehicles in the database. Cannot train model.")
        return

    data = []
    for vehicle in vehicles:
        try:
            data.append({
                'vehicle_type': vehicle.model.sub_category.category.category_name,
                'vehicle_company': vehicle.model.sub_category.company_name,
                'model': vehicle.model.model_name,
                'fuel_type': vehicle.fuel_type,
                'rental_price': float(vehicle.rental_price)
            })
        except AttributeError as e:
            print(f"Error processing vehicle {vehicle.id}: {str(e)}")

    if not data:
        print("No valid data to train the model.")
        return

    df = pd.DataFrame(data)

    # Print unique values for each column
    for column in df.columns:
        print(f"Unique values in {column}: {df[column].unique()}")

    # Encode categorical variables
    le_dict = {}
    for column in ['vehicle_type', 'vehicle_company', 'model', 'fuel_type']:
        le_dict[column] = LabelEncoder()
        df[column] = le_dict[column].fit_transform(df[column])

    # Split the data
    X = df.drop('rental_price', axis=1)
    y = df['rental_price']

    # Train the model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # Save the model and label encoders
    joblib.dump(model, 'vendor/ml_model.joblib')
    joblib.dump(le_dict, 'vendor/label_encoders.joblib')

    print("Model trained and saved successfully.")

def predict_price(vehicle_type, vehicle_company, model, fuel_type):
    # Load the model and label encoders
    try:
        loaded_model = joblib.load('vendor/ml_model.joblib')
        le_dict = joblib.load('vendor/label_encoders.joblib')
    except Exception as e:
        print(f"Error loading model or encoders: {str(e)}")
        return None

    # Encode the input
    input_data = pd.DataFrame({
        'vehicle_type': [vehicle_type],
        'vehicle_company': [vehicle_company],
        'model': [model],
        'fuel_type': [fuel_type]
    })

    for column in input_data.columns:
        le = le_dict.get(column, LabelEncoder())
        if input_data[column][0] not in le.classes_:
            print(f"Warning: Unknown category in {column}: {input_data[column][0]}")
            # Fit the encoder with the new category
            new_classes = np.append(le.classes_, input_data[column][0])
            le.fit(new_classes)
        
        input_data[column] = le.transform(input_data[column])
        le_dict[column] = le

    # Save updated label encoders
    joblib.dump(le_dict, 'vendor/label_encoders.joblib')

    # Make prediction
    try:
        prediction = loaded_model.predict(input_data)
        return prediction[0]
    except Exception as e:
        print(f"Error making prediction: {str(e)}")
        return None
