import joblib

models = {
    "Irrigation": "../model/irrigation_model.pkl",
    "Yield": "../model/yield_model.pkl",
    "Disease": "../model/disease_model.pkl",
    "Heat": "../model/heat_stress_model.pkl",
    "Soil": "../model/soil_health_model.pkl",
    "Fertilizer": "../model/fertilizer_model.pkl",
    "Time": "../model/irrigation_time_model.pkl",
    "Rain": "../model/rain_impact_model.pkl",
    "Farm": "../model/farm_efficiency_model.pkl",
    "Crop": "../model/crop_recommendation_model.pkl"
}

for name, path in models.items():
    print("=" * 60)
    print(name)

    model = joblib.load(path)

    print(model.feature_names_in_)