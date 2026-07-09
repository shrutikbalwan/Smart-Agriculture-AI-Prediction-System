import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

print("="*60)
print("FERTILIZER RECOMMENDATION MODEL")
print("="*60)

data = pd.read_csv("../data/final_dataset.csv")

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
"pesticide_usage_ml",
"total_days",
"latitude",
"longitude",
"NDVI_index"
]
]

y = data["Recommended_Fertilizer"]

X_train,X_test,y_train,y_test = train_test_split(
X,y,test_size=0.20,random_state=42
)

model = RandomForestClassifier(
n_estimators=300,
random_state=42
)

model.fit(X_train,y_train)

prediction=model.predict(X_test)

accuracy=accuracy_score(y_test,prediction)

print("\nAccuracy :",round(accuracy*100,2),"%")

print(classification_report(y_test,prediction))

joblib.dump(model,"../model/fertilizer_model.pkl")

print("\nModel Saved Successfully")