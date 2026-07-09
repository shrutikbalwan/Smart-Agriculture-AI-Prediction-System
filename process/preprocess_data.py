import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder

print("=" * 60)
print("SMART AGRICULTURE DATA PREPROCESSING")
print("=" * 60)

# Load the 20,000-row master dataset
data = pd.read_csv("../data/smart_agriculture_master_dataset_20000.csv")

print("\nDataset Loaded Successfully")

# =====================================
# Fill Missing Values
# =====================================

data["irrigation_type"] = data["irrigation_type"].fillna("Unknown")
data["crop_disease_status"] = data["crop_disease_status"].fillna("Healthy")

print("Missing Values Filled")

# =====================================
# Remove Unnecessary Columns
# =====================================

remove_columns = [
    "farm_id",
    "sensor_id",
    "timestamp",
    "sowing_date",
    "harvest_date"
]

data = data.drop(columns=remove_columns)

print("Unnecessary Columns Removed")

# =====================================
# Encode Text Columns
# =====================================

label_encoders = {}

categorical_columns = [
    "region",
    "crop_type",
    "irrigation_type",
    "fertilizer_type",
    "crop_disease_status",
    "Heat_Stress",
    "Soil_Health",
    "Recommended_Fertilizer",
    "Irrigation_Time",
    "Rain_Impact",
    "Farm_Efficiency"
]

for column in categorical_columns:
    encoder = LabelEncoder()
    data[column] = encoder.fit_transform(data[column].astype(str))
    label_encoders[column] = encoder

print("Encoding Completed")

# =====================================
# Save Label Encoders
# =====================================

joblib.dump(label_encoders, "../model/label_encoders.pkl")

print("Label Encoders Saved")

# =====================================
# Save Final Dataset
# =====================================

data.to_csv("../data/final_dataset.csv", index=False)

print("Final Dataset Saved Successfully")

print("\nDataset Shape:", data.shape)

print("\nColumns:")
print(data.columns)