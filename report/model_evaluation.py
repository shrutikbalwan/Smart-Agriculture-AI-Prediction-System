import os
import pandas as pd
import joblib
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    r2_score,
    mean_absolute_error,
    confusion_matrix,
    ConfusionMatrixDisplay,
    classification_report,
)

# Load dataset
data = pd.read_csv("../data/final_dataset.csv")

MODELS = [
    ("irrigation_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index", "crop_disease_status"
    ], "Water_Needed", "classifier"),
    ("disease_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "crop_disease_status", "classifier"),
    ("heat_stress_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "Heat_Stress", "classifier"),
    ("soil_health_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "Soil_Health", "classifier"),
    ("rain_impact_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "Rain_Impact", "classifier"),
    ("farm_efficiency_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "Farm_Efficiency", "classifier"),
    ("irrigation_time_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index"
    ], "Irrigation_Time", "classifier"),
    ("fertilizer_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "pesticide_usage_ml", "total_days", "latitude", "longitude",
        "NDVI_index"
    ], "Recommended_Fertilizer", "classifier"),
    ("crop_recommendation_model", [
        "region", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "latitude",
        "longitude", "NDVI_index"
    ], "crop_type", "classifier"),
    ("yield_model", [
        "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
        "longitude", "NDVI_index", "crop_disease_status"
    ], "yield_kg_per_hectare", "regressor"),
]

os.makedirs("../report/figures", exist_ok=True)

print("=" * 70)
print("MODEL EVALUATION REPORT")
print("=" * 70)

results = []

for model_name, features, target_col, model_type in MODELS:
    print(f"\n{'=' * 70}")
    print(f"MODEL: {model_name}")

    feature_cols = [c for c in features if c in data.columns]
    if target_col not in data.columns:
        print(f"  SKIP: target '{target_col}' not found")
        continue

    X = data[feature_cols]
    y = data[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    try:
        model = joblib.load(f"../model/{model_name}.pkl")
    except FileNotFoundError:
        print(f"  SKIP: model file not found")
        continue

    prediction = model.predict(X_test)

    if model_type == "regressor":
        mae = mean_absolute_error(y_test, prediction)
        r2 = r2_score(y_test, prediction)
        print(f"  MAE: {round(mae, 2)}")
        print(f"  R2 Score: {round(r2 * 100, 2)}%")
        results.append({
            "model": model_name, "type": model_type,
            "mae": round(mae, 2), "r2": round(r2 * 100, 2),
        })
    else:
        accuracy = accuracy_score(y_test, prediction)
        print(f"  Accuracy: {round(accuracy * 100, 2)}%")
        print(f"\n  Classification Report:")
        print(classification_report(y_test, prediction))

        cm = confusion_matrix(y_test, prediction)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm)
        disp.plot()
        plt.title(f"{model_name} - Confusion Matrix")
        plt.tight_layout()
        plt.savefig(f"../report/figures/{model_name}_confusion_matrix.png", dpi=150)
        plt.close()

        results.append({
            "model": model_name, "type": model_type,
            "accuracy": round(accuracy * 100, 2),
        })

print(f"\n{'=' * 70}")
print("SUMMARY")
print(f"{'=' * 70}")
print(f"{'Model':35s} {'Type':15s} {'Metric':15s} {'Value':10s}")
print("-" * 75)
for r in results:
    if r["type"] == "regressor":
        print(f"{r['model']:35s} {r['type']:15s} {'R2':15s} {r['r2']}%")
    else:
        print(f"{r['model']:35s} {r['type']:15s} {'Accuracy':15s} {r['accuracy']}%")

print(f"\n{'=' * 70}")
print("Evaluation complete. Confusion matrices saved to report/figures/")
print(f"{'=' * 70}")