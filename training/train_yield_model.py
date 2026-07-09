from pathlib import Path

import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

print("=" * 60)
print("YIELD PREDICTION MODEL")
print("=" * 60)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "final_dataset.csv"
MODEL_PATH = BASE_DIR / "model" / "yield_model.pkl"

# Load Dataset
data = pd.read_csv(DATA_PATH)

# Input Features
X = data[
    [
        "region",
        "crop_type",
        "soil_moisture_%",
        "soil_pH",
        "temperature_C",
        "rainfall_mm",
        "humidity_%",
        "sunlight_hours",
        "irrigation_type",
        "fertilizer_type",
        "pesticide_usage_ml",
        "total_days",
        "latitude",
        "longitude",
        "NDVI_index",
        "crop_disease_status"
    ]
]

# Target
y = data["yield_kg_per_hectare"]

# Split Dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

# Create Model
model = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)

# Train
model.fit(X_train, y_train)

# Predict
prediction = model.predict(X_test)

# Evaluation
mae = mean_absolute_error(y_test, prediction)
r2 = r2_score(y_test, prediction)

print("\nMean Absolute Error :", round(mae,2))
print("R2 Score :", round(r2*100,2), "%")

# Save Model
joblib.dump(model, MODEL_PATH, compress=3)

print(f"\nYield Model Saved Successfully at {MODEL_PATH}")