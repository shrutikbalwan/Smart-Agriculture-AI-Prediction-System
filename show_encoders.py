import joblib

encoders = joblib.load("model/label_encoders.pkl")

print("=" * 60)

for name, encoder in encoders.items():

    print("\nEncoder :", name)
    print("Classes :", list(encoder.classes_))

print("=" * 60)