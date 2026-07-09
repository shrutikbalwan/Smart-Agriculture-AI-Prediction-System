import json
import sys
import traceback
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"
passed = 0
failed = 0
results = []

def request(method, path, body=None, headers=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if data:
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    else:
        req = urllib.request.Request(url, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except Exception as e:
        return 0, str(e)

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        results.append((name, "PASS", ""))
    except AssertionError as e:
        failed += 1
        results.append((name, "FAIL", str(e)))
    except Exception as e:
        failed += 1
        results.append((name, "ERROR", traceback.format_exc()))

def check(cond, msg=""):
    if not cond:
        raise AssertionError(msg)

VALID_PAYLOAD = {
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
    "NDVI_index": 0.65,
}

# ── HEALTH ──
def test_health():
    status, data = request("GET", "/health")
    check(status == 200, f"Expected 200 got {status}")
    check(data.get("success") is True)
    check(data.get("status") == "healthy")
    check("models_loaded" in data)
    check("database" in data)
    check("timestamp" in data)

# ── PREDICT ──
def test_predict_success():
    status, data = request("POST", "/predict", VALID_PAYLOAD)
    check(status == 200, f"Expected 200 got {status}")
    check(data.get("success") is True, "Expected success True")
    p = data.get("prediction", {})
    check("CropRecommendation" in p)
    check("PredictedYield(Kg/Hectare)" in p)
    check("Disease" in p)
    check("HeatStress" in p)
    check("SoilHealth" in p)
    check("Fertilizer" in p)
    check("IrrigationTime" in p)
    check("RainImpact" in p)
    check("FarmEfficiency" in p)
    check("Irrigation" in p)
    check("PredictionTime" in p)
    check("ModelVersion" in p)
    check("Confidence" in p)
    check(p["ModelVersion"] == "v1.0")

def test_predict_missing_field():
    incomplete = {k: v for k, v in VALID_PAYLOAD.items() if k != "region"}
    status, data = request("POST", "/predict", incomplete)
    check(status == 400, f"Expected 400 got {status}")
    check("Missing required fields" in data.get("error", ""))

def test_predict_invalid_encoder():
    bad = dict(VALID_PAYLOAD)
    bad["region"] = "INVALID_REGION_XYZ"
    status, data = request("POST", "/predict", bad)
    check(status == 400, f"Expected 400 got {status}")
    check("Invalid" in data.get("error", ""))
    check("Allowed" in data.get("error", ""))

def test_predict_empty_body():
    status, data = request("POST", "/predict", {})
    check(status == 400, f"Expected 400 got {status}")

def test_predict_wrong_method():
    status, data = request("GET", "/predict")
    check(status == 405, f"Expected 405 got {status}")

# ── HISTORY ──
def test_history_meta():
    status, data = request("GET", "/history/meta")
    check(status in (200, 503), f"Expected 200/503 got {status}")
    if status == 200:
        check(data.get("success") is True)
        check("regions" in data)
        check("crops" in data)

def test_history_list():
    status, data = request("GET", "/history")
    check(status in (200, 503), f"Expected 200/503 got {status}")
    if status == 200:
        check(data.get("success") is True)
        check("data" in data)
        check("pagination" in data)

def test_history_with_filters():
    status, data = request("GET", "/history?page=1&per_page=5&region=South+India")
    check(status in (200, 503), f"Expected 200/503 got {status}")

def test_history_invalid_page():
    status, data = request("GET", "/history?page=-1")
    check(status in (200, 503), f"Expected 200/503 got {status}")

# ── EXPORT ──
def test_export_csv():
    status, data = request("GET", "/export/csv")
    check(status in (200, 503), f"Expected 200/503 got {status}")

def test_export_excel():
    status, data = request("GET", "/export/excel")
    check(status in (200, 503), f"Expected 200/503 got {status}")

# ── DASHBOARD ──
def test_dashboard_stats():
    status, data = request("GET", "/dashboard/stats")
    check(status in (200, 503), f"Expected 200/503 got {status}")
    if status == 200:
        check(data.get("success") is True)
        s = data.get("stats", {})
        check("total_predictions" in s)
        check("average_yield" in s)
        check("daily_predictions" in s)
        check("crop_distribution" in s)

# ── WEATHER ──
def test_weather_current_no_key():
    status, data = request("GET", "/weather/current?lat=28.61&lon=77.23")
    check(status in (503, 400), f"Expected 503/400 got {status}")

def test_weather_current_missing_params():
    status, data = request("GET", "/weather/current")
    check(status == 400, f"Expected 400 got {status}")

def test_weather_forecast_missing_params():
    status, data = request("GET", "/weather/forecast")
    check(status == 400, f"Expected 400 got {status}")

# ── AUTH ──
def test_auth_register_missing_fields():
    status, data = request("POST", "/auth/register", {})
    check(status in (400, 503), f"Expected 400/503 got {status}")

def test_auth_login_missing_fields():
    status, data = request("POST", "/auth/login", {})
    check(status in (400, 503), f"Expected 400/503 got {status}")

def test_auth_me_no_token():
    status, data = request("GET", "/auth/me")
    check(status in (401, 503), f"Expected 401/503 got {status}")

# ── DELETE ──
def test_delete_nonexistent():
    status, data = request("DELETE", "/history/999999")
    check(status in (404, 503), f"Expected 404/503 got {status}")

# ── RUN ALL ──
tests = [
    ("Health Check", test_health),
    ("Predict - Valid Input", test_predict_success),
    ("Predict - Missing Fields", test_predict_missing_field),
    ("Predict - Invalid Encoder Value", test_predict_invalid_encoder),
    ("Predict - Empty Body", test_predict_empty_body),
    ("Predict - Wrong Method (GET)", test_predict_wrong_method),
    ("History - Meta Endpoint", test_history_meta),
    ("History - List", test_history_list),
    ("History - With Filters", test_history_with_filters),
    ("History - Invalid Page", test_history_invalid_page),
    ("Export - CSV", test_export_csv),
    ("Export - Excel", test_export_excel),
    ("Dashboard - Stats", test_dashboard_stats),
    ("Weather - No API Key", test_weather_current_no_key),
    ("Weather - Missing Params", test_weather_current_missing_params),
    ("Weather Forecast - Missing Params", test_weather_forecast_missing_params),
    ("Auth - Register Missing Fields", test_auth_register_missing_fields),
    ("Auth - Login Missing Fields", test_auth_login_missing_fields),
    ("Auth - No Token", test_auth_me_no_token),
    ("Delete - Non-existent Record", test_delete_nonexistent),
]

print("=" * 70)
print("SMART AGRICULTURE - COMPREHENSIVE API TEST SUITE")
print("=" * 70)

for name, fn in tests:
    test(name, fn)

print(f"\n{'=' * 70}")
print(f"RESULTS: {passed}/{passed + failed} passed, {failed} failed")
print(f"{'=' * 70}\n")

for name, status, detail in results:
    icon = "+" if status == "PASS" else "x"
    print(f"  [{icon}] {name} ({status})")
    if detail:
        print(f"       {detail[:200]}")
