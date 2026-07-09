"""
Cross-validation and feature importance analysis for all models.
Run: python training/cross_validate.py
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import cross_val_score, KFold

BASE_DIR = "."
DATA_PATH = f"{BASE_DIR}/data/final_dataset.csv"
MODEL_DIR = f"{BASE_DIR}/model"

data = pd.read_csv(DATA_PATH)

MODELS_CONFIG = [
    ("irrigation_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                           "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                           "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                           "longitude", "NDVI_index", "crop_disease_status"], "Water_Needed", "classifier"),
    ("disease_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                        "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                        "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                        "longitude", "NDVI_index"], "crop_disease_status", "classifier"),
    ("heat_stress_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                            "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                            "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                            "longitude", "NDVI_index"], "Heat_Stress", "classifier"),
    ("soil_health_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                            "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                            "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                            "longitude", "NDVI_index"], "Soil_Health", "classifier"),
    ("rain_impact_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                            "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                            "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                            "longitude", "NDVI_index"], "Rain_Impact", "classifier"),
    ("farm_efficiency_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                                "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                                "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                                "longitude", "NDVI_index"], "Farm_Efficiency", "classifier"),
    ("irrigation_time_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                                "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                                "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                                "longitude", "NDVI_index"], "Irrigation_Time", "classifier"),
    ("fertilizer_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                           "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                           "pesticide_usage_ml", "total_days", "latitude", "longitude",
                           "NDVI_index"], "Recommended_Fertilizer", "classifier"),
    ("crop_recommendation_model", ["region", "soil_moisture_%", "soil_pH", "temperature_C",
                                    "rainfall_mm", "humidity_%", "sunlight_hours", "latitude",
                                    "longitude", "NDVI_index"], "crop_type", "classifier"),
    ("yield_model", ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                      "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                      "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
                      "longitude", "NDVI_index", "crop_disease_status"], "yield_kg_per_hectare", "regressor"),
]

print("=" * 70)
print("CROSS-VALIDATION & FEATURE IMPORTANCE REPORT")
print("=" * 70)

kfold = KFold(n_splits=5, shuffle=True, random_state=42)

for model_name, features, target_col, model_type in MODELS_CONFIG:
    print(f"\n{'=' * 70}")
    print(f"MODEL: {model_name}")

    feature_cols = [c for c in features if c in data.columns]
    if target_col not in data.columns:
        print(f"  SKIP: target '{target_col}' not in dataset")
        continue

    X = data[feature_cols]
    y = data[target_col]

    try:
        model = joblib.load(f"{MODEL_DIR}/{model_name}.pkl")
    except FileNotFoundError:
        print(f"  SKIP: model file not found")
        continue

    scoring = "r2" if model_type == "regressor" else "accuracy"
    scores = cross_val_score(model.__class__(**model.get_params()), X, y, cv=kfold, scoring=scoring)
    print(f"  Cross-val {scoring}: {scores}")
    print(f"  Mean: {scores.mean():.4f} (+/- {scores.std() * 2:.4f})")

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        print(f"  Feature Importances (top-5):")
        for i in range(min(5, len(feature_cols))):
            print(f"    {i + 1}. {feature_cols[indices[i]]}: {importances[indices[i]]:.4f}")
    else:
        print(f"  Feature importance not available for this model")

print(f"\n{'=' * 70}")
print("Cross-validation complete")
print(f"{'=' * 70}")
