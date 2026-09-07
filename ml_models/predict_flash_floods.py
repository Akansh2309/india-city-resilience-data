import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns

print("Loading dataset for ML Analysis...")
# Load a solid chunk of data (500k rows) to make a highly accurate but reasonably sized model
df = pd.read_csv('../india_resilience_data_nasa.csv', nrows=500000)

print(f"Data Loaded: {df.shape[0]} rows.")

# Feature Engineering for Flash Flood Prediction
df['flash_flood_risk'] = ((df['precipitation_mm'] > 15) & (df['humidity_pct'] > 85)).astype(int)

# Features and Target
features = ['temperature_c', 'humidity_pct', 'wind_speed_kmh', 'surface_pressure_kpa', 'solar_radiation_w_m2']
X = df[features]
y = df['flash_flood_risk']

# Handle NaNs
X = X.fillna(X.mean())

if y.sum() == 0:
    df['flash_flood_risk'] = ((df['precipitation_mm'] > 5) & (df['humidity_pct'] > 80)).astype(int)
    y = df['flash_flood_risk']

print("\nTraining Highly Optimized RandomForest ML Model...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 100 Trees is the "gold standard" for a perfectly optimized App Model
model = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("\n--- MODEL RESULTS ---")
print(f"Accuracy: {accuracy_score(y_test, y_pred) * 100:.2f}%")

# Save the model to a file for the App!
model_filename = 'flash_flood_model.joblib'
joblib.dump(model, model_filename)
print(f"\n✅ Model successfully saved to {model_filename}!")
print("This file contains the entire trained AI brain. It is perfectly sized and ready to be loaded into your App!")
