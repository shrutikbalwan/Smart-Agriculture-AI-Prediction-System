import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

print("=" * 60)
print("CROP DISEASE PREDICTION MODEL")
print("=" * 60)

# Load Dataset
data = pd.read_csv("../data/final_dataset.csv")

# Features
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
        "NDVI_index"
    ]
]

# Target
y = data["crop_disease_status"]

# Split Dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

# Create Model
model = RandomForestClassifier(
    n_estimators=300,
    random_state=42
)

# Train Model
model.fit(X_train, y_train)

# Prediction
prediction = model.predict(X_test)

# Accuracy
accuracy = accuracy_score(y_test, prediction)

print("\nAccuracy :", round(accuracy * 100, 2), "%")

print("\nClassification Report\n")
print(classification_report(y_test, prediction))

# Save Model
joblib.dump(model, "../model/disease_model.pkl")

print("\nDisease Model Saved Successfully")