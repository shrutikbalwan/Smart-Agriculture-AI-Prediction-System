from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "final_dataset.csv"
MODEL_DIR = BASE_DIR / "model"
FIGURE_DIR = BASE_DIR / "report" / "figures"
RANDOM_STATE = 42
TEST_SIZE = 0.20

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


def evaluate_models():
    np.random.seed(RANDOM_STATE)
    data = pd.read_csv(DATA_PATH)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    print("=" * 80)
    print("SMART AGRICULTURE ML EVALUATION")
    print("=" * 80)
    print(f"Dataset       : {DATA_PATH}")
    print(f"Model folder  : {MODEL_DIR}")
    print(f"Split         : test_size={TEST_SIZE}, random_state={RANDOM_STATE}")

    for model_name, features, target_col, model_type in MODELS:
        print(f"\n{'=' * 80}")
        print(f"MODEL: {model_name}")

        model_path = MODEL_DIR / f"{model_name}.pkl"
        if not model_path.exists():
            print(f"SKIP: model file not found at {model_path}")
            continue
        model = joblib.load(model_path)

        expected_features = list(getattr(model, "feature_names_in_", features))
        missing_features = [column for column in expected_features if column not in data.columns]
        if target_col not in data.columns:
            print(f"SKIP: target column '{target_col}' not found in dataset")
            continue
        if missing_features:
            print(f"SKIP: missing required feature columns: {missing_features}")
            continue

        X = data[expected_features]
        y = data[target_col]

        split_kwargs = {"test_size": TEST_SIZE, "random_state": RANDOM_STATE}
        if model_type == "classifier":
            split_kwargs["stratify"] = y

        try:
            _, X_test, _, y_test = train_test_split(X, y, **split_kwargs)
        except ValueError as split_error:
            if model_type == "classifier" and "least populated class" in str(split_error):
                print("WARN: stratified split unavailable (rare class count too small), using deterministic non-stratified split")
                split_kwargs.pop("stratify", None)
                _, X_test, _, y_test = train_test_split(X, y, **split_kwargs)
            else:
                print(f"SKIP: failed to split dataset: {split_error}")
                continue
        y_pred = model.predict(X_test)

        if model_type == "regressor":
            mae = mean_absolute_error(y_test, y_pred)
            rmse = mean_squared_error(y_test, y_pred) ** 0.5
            r2 = r2_score(y_test, y_pred)

            print(f"MAE : {mae:.4f}")
            print(f"RMSE: {rmse:.4f}")
            print(f"R²  : {r2:.4f}")

            results.append({
                "model": model_name,
                "type": model_type,
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
            })
            continue

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        print(f"Accuracy : {accuracy:.4f}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall   : {recall:.4f}")
        print(f"F1-score : {f1:.4f}")
        print("\nClassification report:")
        print(classification_report(y_test, y_pred, zero_division=0))

        labels = sorted(pd.Series(y_test).astype(str).unique())
        cm = confusion_matrix(y_test.astype(str), y_pred.astype(str), labels=labels)
        cm_df = pd.DataFrame(cm, index=labels, columns=labels)
        print("Confusion matrix:")
        print(cm_df.to_string())

        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
        fig, ax = plt.subplots(figsize=(8, 6))
        disp.plot(ax=ax, xticks_rotation=45, colorbar=False)
        ax.set_title(f"{model_name} - Confusion Matrix")
        fig.tight_layout()
        figure_path = FIGURE_DIR / f"{model_name}_confusion_matrix.png"
        fig.savefig(figure_path, dpi=150)
        plt.close(fig)
        print(f"Confusion matrix image: {figure_path}")

        results.append({
            "model": model_name,
            "type": model_type,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        })

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)
    for result in results:
        if result["type"] == "regressor":
            print(
                f"{result['model']}: "
                f"MAE={result['mae']:.4f}, RMSE={result['rmse']:.4f}, R²={result['r2']:.4f}"
            )
        else:
            print(
                f"{result['model']}: "
                f"Accuracy={result['accuracy']:.4f}, "
                f"Precision={result['precision']:.4f}, "
                f"Recall={result['recall']:.4f}, "
                f"F1={result['f1']:.4f}"
            )
    print("=" * 80)
    print(f"Done. Confusion matrix figures saved to: {FIGURE_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    evaluate_models()