import json
import urllib.request

url = "http://127.0.0.1:5000/predict"

payload = {
    "region": "South India",
    "crop_type": "Rice",
    "soil_moisture_%": 45.2,
    "soil_pH": 6.5,
    "temperature_C": 28.5,
    "rainfall_mm": 120.0,
    "humidity_%": 75.0,
    "sunlight_hours": 8.0,
    "irrigation_type": "Drip",
    "fertilizer_type": "Organic",
    "pesticide_usage_ml": 250.0,
    "total_days": 120,
    "latitude": 12.34,
    "longitude": 78.56,
    "NDVI_index": 0.65
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"Status: {resp.status}")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode("utf-8"))
except Exception as e:
    print(f"Error: {e}")
