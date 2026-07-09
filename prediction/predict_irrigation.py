import pandas as pd
import joblib

# =====================================
# Load Model
# =====================================

model = joblib.load("../model/irrigation_model.pkl")

# Load Label Encoders
label_encoders = joblib.load("../model/label_encoders.pkl")

print("Model Loaded Successfully")

# =====================================
# User Input
# =====================================

region = input("Region : ")
crop_type = input("Crop Type : ")
soil_moisture = float(input("Soil Moisture (%) : "))
soil_pH = float(input("Soil pH : "))
temperature = float(input("Temperature (°C) : "))
rainfall = float(input("Rainfall (mm) : "))
humidity = float(input("Humidity (%) : "))
sunlight = float(input("Sunlight Hours : "))
irrigation_type = input("Irrigation Type : ")
fertilizer_type = input("Fertilizer Type : ")
pesticide = float(input("Pesticide Usage (ml) : "))
total_days = int(input("Crop Age (Days) : "))
latitude = float(input("Latitude : "))
longitude = float(input("Longitude : "))
ndvi = float(input("NDVI Index : "))
disease = input("Crop Disease Status : ")

# =====================================
# Convert Text to Numbers
# =====================================

region = label_encoders["region"].transform([region])[0]
crop_type = label_encoders["crop_type"].transform([crop_type])[0]
irrigation_type = label_encoders["irrigation_type"].transform([irrigation_type])[0]
fertilizer_type = label_encoders["fertilizer_type"].transform([fertilizer_type])[0]
disease = label_encoders["crop_disease_status"].transform([disease])[0]

# =====================================
# Create Input DataFrame
# =====================================

sample = pd.DataFrame([{
    "region": region,
    "crop_type": crop_type,
    "soil_moisture_%": soil_moisture,
    "soil_pH": soil_pH,
    "temperature_C": temperature,
    "rainfall_mm": rainfall,
    "humidity_%": humidity,
    "sunlight_hours": sunlight,
    "irrigation_type": irrigation_type,
    "fertilizer_type": fertilizer_type,
    "pesticide_usage_ml": pesticide,
    "total_days": total_days,
    "latitude": latitude,
    "longitude": longitude,
    "NDVI_index": ndvi,
    "crop_disease_status": disease
}])

# =====================================
# Prediction
# =====================================

prediction = model.predict(sample)

print("\n=================================")

if prediction[0] == 1:
    print("💧 Irrigation Required")
else:
    print("✅ Irrigation Not Required")

print("=================================")