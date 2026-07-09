import joblib
import pandas as pd

print("="*60)
print("SMART AGRICULTURE AI ENGINE")
print("="*60)

print("\nLoading Models...")

irrigation_model = joblib.load("../model/irrigation_model.pkl")
yield_model = joblib.load("../model/yield_model.pkl")
disease_model = joblib.load("../model/disease_model.pkl")
heat_model = joblib.load("../model/heat_stress_model.pkl")
soil_model = joblib.load("../model/soil_health_model.pkl")
fertilizer_model = joblib.load("../model/fertilizer_model.pkl")
time_model = joblib.load("../model/irrigation_time_model.pkl")
rain_model = joblib.load("../model/rain_impact_model.pkl")
farm_model = joblib.load("../model/farm_efficiency_model.pkl")
crop_model = joblib.load("../model/crop_recommendation_model.pkl")

encoders = joblib.load("../model/label_encoders.pkl")

print("All Models Loaded Successfully")