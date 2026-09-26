import hashlib
import io
import json
import logging
import os
import secrets
from collections import Counter
from datetime import date, datetime

import joblib
import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify, request, send_file
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)

# Works both as a package (gunicorn backend.app:app) and as a script/tests (python app.py)
try:
    from .db import get_db
    from . import agronomy
    from .weather_service import fetch_forecast_summary
except ImportError:  # pragma: no cover - exercised depending on how the app is launched
    from db import get_db
    import agronomy
    from weather_service import fetch_forecast_summary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "..", "model")

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"


def _secret(name):
    """Secrets are mandatory in production; development gets a random per-process value."""
    value = os.getenv(name)
    if value:
        return value
    if IS_PRODUCTION:
        raise RuntimeError(f"{name} must be set when APP_ENV=production")
    return secrets.token_hex(32)


app = Flask(__name__)
app.config["SECRET_KEY"] = _secret("FLASK_SECRET_KEY")
app.config["JWT_SECRET_KEY"] = _secret("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400

_cors_env = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] or ([] if IS_PRODUCTION else "*")
CORS(app, origins=CORS_ORIGINS)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logger.info("Loading AI models...")
irrigation_model = joblib.load(os.path.join(MODEL_DIR, "irrigation_model.pkl"))
yield_model = joblib.load(os.path.join(MODEL_DIR, "yield_model.pkl"))
disease_model = joblib.load(os.path.join(MODEL_DIR, "disease_model.pkl"))
heat_model = joblib.load(os.path.join(MODEL_DIR, "heat_stress_model.pkl"))
soil_model = joblib.load(os.path.join(MODEL_DIR, "soil_health_model.pkl"))
fertilizer_model = joblib.load(os.path.join(MODEL_DIR, "fertilizer_model.pkl"))
time_model = joblib.load(os.path.join(MODEL_DIR, "irrigation_time_model.pkl"))
rain_model = joblib.load(os.path.join(MODEL_DIR, "rain_impact_model.pkl"))
farm_model = joblib.load(os.path.join(MODEL_DIR, "farm_efficiency_model.pkl"))
crop_model = joblib.load(os.path.join(MODEL_DIR, "crop_recommendation_model.pkl"))
encoders = joblib.load(os.path.join(MODEL_DIR, "label_encoders.pkl"))
logger.info("All models loaded successfully")

OWM_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")

REQUIRED_FIELDS = [
    "region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
    "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
    "fertilizer_type", "pesticide_usage_ml", "total_days", "latitude",
    "longitude", "NDVI_index",
]

CLASSIFIER_MODELS = {
    "irrigation": irrigation_model, "disease": disease_model,
    "heat": heat_model, "soil": soil_model, "fertilizer": fertilizer_model,
    "irrigation_time": time_model, "rain": rain_model, "farm": farm_model,
    "crop": crop_model,
}

HISTORY_SEARCH_FIELDS = [
    "region", "crop_type", "crop_recommendation", "disease_prediction",
    "heat_stress", "soil_health", "fertilizer_recommendation",
    "irrigation_time", "rain_impact", "farm_efficiency", "confidence",
    "predicted_yield",
]

HISTORY_DATE_FIELDS = [
    "prediction_time", "created_at", "timestamp", "date_created",
    "datetime_created", "prediction_date", "createdOn",
]

HISTORY_DISTINCT_FILTERS = {
    "regions": "region", "crops": "crop_type",
    "recommended_crops": "crop_recommendation", "diseases": "disease_prediction",
}


def compute_confidence(model, input_data):
    try:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(input_data)
            return f"{round(float(np.max(proba[0])) * 100, 2)}%"
    except Exception:
        pass
    return None


def serialize_value(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def get_history_schema(db_conn):
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("SHOW COLUMNS FROM prediction_history")
        columns = cursor.fetchall()
    finally:
        cursor.close()
    column_names = [c["Field"] for c in columns]
    return {
        "columns": column_names,
        "primary_key": next((c["Field"] for c in columns if c.get("Key") == "PRI"), None),
        "date_column": next((f for f in HISTORY_DATE_FIELDS if f in column_names), None),
        "order_column": next((
            c["Field"] for c in columns if c.get("Key") == "PRI"
        ), next((f for f in HISTORY_DATE_FIELDS if f in column_names), column_names[0] if column_names else None)),
    }


def build_history_where_clause(filters, available_columns, date_column):
    clauses, params = [], []
    search = (filters.get("search") or "").strip()
    if search:
        cols = [c for c in HISTORY_SEARCH_FIELDS if c in available_columns]
        if cols:
            clauses.append("(" + " OR ".join(f"CAST(`{c}` AS CHAR) LIKE %s" for c in cols) + ")")
            params.extend([f"%{search}%"] * len(cols))
    for key, col in [("region", "region"), ("crop", "crop_type"), ("disease", "disease_prediction")]:
        val = (filters.get(key) or "").strip()
        if val and col in available_columns:
            clauses.append(f"`{col}` = %s")
            params.append(val)
    for key in ["start_date", "end_date"]:
        val = (filters.get(key) or "").strip()
        if val and date_column:
            op = ">=" if key == "start_date" else "<="
            clauses.append(f"DATE(`{date_column}`) {op} %s")
            params.append(val)
    return (f" WHERE {' AND '.join(clauses)}", params) if clauses else ("", params)


def log_audit(user_id, action, entity_type=None, entity_id=None, details=None, ip=None):
    db_conn, db_cursor = get_db()
    if db_cursor is None:
        return
    try:
        db_cursor.execute(
            "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, action, entity_type, entity_id, json.dumps(details, default=str) if details else None, ip),
        )
        db_conn.commit()
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


# ===================== HEALTH =====================

@app.route("/health", methods=["GET"])
def health_check():
    db_conn, _ = get_db()
    db_status = "connected" if db_conn else "unavailable"
    return jsonify({
        "success": True,
        "status": "healthy",
        "database": db_status,
        "models_loaded": len(CLASSIFIER_MODELS) + 1,
        "timestamp": datetime.now().isoformat(),
    })


# ===================== AUTH =====================

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not username or not email or not password:
        return jsonify({"success": False, "error": "username, email, password required"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400
    db_conn, db_cursor = get_db()
    if db_cursor is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        db_cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if db_cursor.fetchone():
            return jsonify({"success": False, "error": "Username or email already exists"}), 409
        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        db_cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, pw_hash),
        )
        db_conn.commit()
        user_id = db_cursor.lastrowid
        db_cursor.execute("INSERT INTO user_settings (user_id) VALUES (%s)", (user_id,))
        db_conn.commit()
        log_audit(user_id, "register", "user", user_id, {"username": username}, request.remote_addr)
        return jsonify({"success": True, "user_id": user_id}), 201
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db_conn, db_cursor = get_db()
    if db_cursor is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        db_cursor.execute("SELECT id, username, email, password_hash, role FROM users WHERE username = %s", (username,))
        user = db_cursor.fetchone()
        if not user or not bcrypt.check_password_hash(user["password_hash"], password):
            return jsonify({"success": False, "error": "Invalid credentials"}), 401
        token = create_access_token(identity=str(user["id"]))
        log_audit(user["id"], "login", "user", user["id"], None, request.remote_addr)
        return jsonify({
            "success": True,
            "token": token,
            "user": {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]},
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/auth/me", methods=["GET"])
@jwt_required()
def auth_me():
    user_id = int(get_jwt_identity())
    db_conn, db_cursor = get_db()
    if db_cursor is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        db_cursor.execute("SELECT id, username, email, role, created_at FROM users WHERE id = %s", (user_id,))
        user = db_cursor.fetchone()
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        return jsonify({"success": True, "user": {k: serialize_value(v) for k, v in user.items()}})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ===================== WEATHER PROXY =====================

@app.route("/weather/current", methods=["GET"])
def weather_current():
    if not OWM_API_KEY:
        return jsonify({"success": False, "error": "OpenWeatherMap API key not configured"}), 503
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return jsonify({"success": False, "error": "lat and lon parameters required"}), 400
    try:
        resp = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric"},
            timeout=10,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


@app.route("/weather/forecast", methods=["GET"])
def weather_forecast():
    if not OWM_API_KEY:
        return jsonify({"success": False, "error": "OpenWeatherMap API key not configured"}), 503
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return jsonify({"success": False, "error": "lat and lon parameters required"}), 400
    try:
        resp = requests.get(
            f"https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric"},
            timeout=10,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


# ===================== PREDICT =====================

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "error": "Request body must be JSON"}), 400
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400
        for col in ["region", "crop_type", "irrigation_type", "fertilizer_type"]:
            raw_val = data[col]
            try:
                data[col] = encoders[col].transform([raw_val])[0]
            except ValueError:
                return jsonify({"success": False, "error": f"Invalid '{raw_val}' for '{col}'. Allowed: {list(encoders[col].classes_)}"}), 400
        input_data = pd.DataFrame([[data[f] for f in REQUIRED_FIELDS]], columns=REQUIRED_FIELDS)
        irrigation = irrigation_model.predict(input_data)[0]
        irrigation_status = "Start Irrigation" if irrigation == 1 else "No Irrigation Needed"
        disease = disease_model.predict(input_data)[0]
        yield_input = input_data.copy()
        expected = list(getattr(yield_model, "feature_names_in_", [])) or REQUIRED_FIELDS
        if "crop_disease_status" in expected:
            yield_input["crop_disease_status"] = disease
        yield_input = yield_input.reindex(columns=expected, fill_value=0)
        yield_prediction = yield_model.predict(yield_input)[0]
        heat = heat_model.predict(input_data)[0]
        heat_decoded = encoders["Heat_Stress"].inverse_transform([heat])[0]
        soil = soil_model.predict(input_data)[0]
        soil_decoded = encoders["Soil_Health"].inverse_transform([soil])[0]
        fert_cols = ["region", "crop_type", "soil_moisture_%", "soil_pH", "temperature_C",
                      "rainfall_mm", "humidity_%", "sunlight_hours", "irrigation_type",
                      "pesticide_usage_ml", "total_days", "latitude", "longitude", "NDVI_index"]
        fertilizer = fertilizer_model.predict(input_data[fert_cols])[0]
        fertilizer_decoded = encoders["Recommended_Fertilizer"].inverse_transform([fertilizer])[0]
        irrigation_time = time_model.predict(input_data)[0]
        irrigation_time_decoded = encoders["Irrigation_Time"].inverse_transform([irrigation_time])[0]
        rain = rain_model.predict(input_data)[0]
        rain_decoded = encoders["Rain_Impact"].inverse_transform([rain])[0]
        farm = farm_model.predict(input_data)[0]
        farm_decoded = encoders["Farm_Efficiency"].inverse_transform([farm])[0]
        crop_cols = ["region", "soil_moisture_%", "soil_pH", "temperature_C",
                      "rainfall_mm", "humidity_%", "sunlight_hours", "latitude", "longitude", "NDVI_index"]
        crop = crop_model.predict(input_data[crop_cols])[0]
        crop_decoded = encoders["crop_type"].inverse_transform([crop])[0]
        disease_decoded = encoders["crop_disease_status"].inverse_transform([disease])[0]
        confidence = None
        for key in ["disease", "irrigation", "heat", "soil"]:
            score = compute_confidence(CLASSIFIER_MODELS[key], input_data)
            if score is not None:
                confidence = score
                break
        try:
            original = request.get_json()
            db_conn, db_cursor = get_db()
            if db_cursor and db_conn:
                db_cursor.execute("""
                    INSERT INTO prediction_history (region, crop_type, soil_moisture, soil_ph, temperature,
                    rainfall, humidity, sunlight_hours, irrigation_type, fertilizer_type,
                    pesticide_usage, total_days, latitude, longitude, ndvi_index,
                    crop_recommendation, predicted_yield, disease_prediction, heat_stress,
                    soil_health, fertilizer_recommendation, irrigation_time, rain_impact, farm_efficiency, confidence)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    original.get("region"), original.get("crop_type"), original.get("soil_moisture_%"),
                    original.get("soil_pH"), original.get("temperature_C"), original.get("rainfall_mm"),
                    original.get("humidity_%"), original.get("sunlight_hours"), original.get("irrigation_type"),
                    original.get("fertilizer_type"), original.get("pesticide_usage_ml"), original.get("total_days"),
                    original.get("latitude"), original.get("longitude"), original.get("NDVI_index"),
                    crop_decoded, round(float(yield_prediction), 2), disease_decoded, heat_decoded,
                    soil_decoded, fertilizer_decoded, irrigation_time_decoded, rain_decoded, farm_decoded, confidence,
                ))
                db_conn.commit()
                logger.info("Prediction saved to history")
        except Exception as e:
            logger.warning("DB save skipped: %s", e)
        return jsonify({
            "success": True,
            "prediction": {
                "Irrigation": irrigation_status,
                "PredictedYield(Kg/Hectare)": round(float(yield_prediction), 2),
                "Disease": disease_decoded, "HeatStress": heat_decoded,
                "SoilHealth": soil_decoded, "Fertilizer": fertilizer_decoded,
                "IrrigationTime": irrigation_time_decoded, "RainImpact": rain_decoded,
                "FarmEfficiency": farm_decoded, "CropRecommendation": crop_decoded,
                "PredictionTime": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "ModelVersion": "v1.0", "Confidence": confidence or "N/A",
            },
            "notice": "Legacy demo models trained on a synthetic dataset; use /v2/advise for irrigation decisions.",
        })
    except Exception as exc:
        logger.error("Prediction error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ===================== HISTORY =====================

@app.route("/history/meta", methods=["GET"])
def history_meta():
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        schema = get_history_schema(db_conn)
        cols = schema["columns"]
        date_col = schema["date_column"]
        meta = {"success": True, "regions": [], "crops": [], "recommended_crops": [], "diseases": [], "date_range": {"min": None, "max": None}}
        cursor = db_conn.cursor(dictionary=True)
        try:
            for key, col_name in HISTORY_DISTINCT_FILTERS.items():
                if col_name not in cols:
                    continue
                cursor.execute(f"SELECT DISTINCT `{col_name}` AS v FROM prediction_history WHERE `{col_name}` IS NOT NULL AND `{col_name}` <> '' ORDER BY `{col_name}`")
                meta[key] = [r["v"] for r in cursor.fetchall() if r.get("v")]
            if date_col:
                cursor.execute(f"SELECT MIN(`{date_col}`) AS mn, MAX(`{date_col}`) AS mx FROM prediction_history")
                row = cursor.fetchone() or {}
                meta["date_range"] = {"min": serialize_value(row.get("mn")), "max": serialize_value(row.get("mx"))}
        finally:
            cursor.close()
        return jsonify(meta)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/history", methods=["GET"])
def history_list():
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        schema = get_history_schema(db_conn)
        cols = schema["columns"]
        date_col = schema["date_column"]
        order_col = schema["order_column"]
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 10))))
        sort_col = request.args.get("sort", "")
        sort_dir = "ASC" if request.args.get("order", "").upper() == "ASC" else "DESC"
        filters = {k: request.args.get(k, "") for k in ["search", "region", "crop", "disease", "start_date", "end_date"]}
        where_sql, params = build_history_where_clause(filters, cols, date_col)
        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT COUNT(*) AS total FROM prediction_history{where_sql}", params)
            total = int((cursor.fetchone() or {}).get("total", 0))
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            offset = (page - 1) * per_page
            sort_column = sort_col if sort_col in cols else order_col
            cursor.execute(
                f"SELECT * FROM prediction_history{where_sql} ORDER BY `{sort_column}` {sort_dir} LIMIT %s OFFSET %s",
                params + [per_page, offset],
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
        records = []
        for row in rows:
            normalized = {k: serialize_value(v) for k, v in row.items()}
            normalized["Date"] = normalized.get(date_col) if date_col and date_col in normalized else None
            records.append(normalized)
        return jsonify({"success": True, "data": records, "pagination": {"page": page, "per_page": per_page, "total": total, "total_pages": total_pages}})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/history/<int:record_id>", methods=["DELETE"])
@jwt_required()
def delete_history_entry(record_id):
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        schema = get_history_schema(db_conn)
        pk = schema["primary_key"] or ("id" if "id" in schema["columns"] else None)
        if pk is None:
            return jsonify({"success": False, "error": "Cannot determine id column"}), 500
        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM prediction_history WHERE `{pk}` = %s", (record_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({"success": False, "error": "Record not found"}), 404
            cursor.execute(f"DELETE FROM prediction_history WHERE `{pk}` = %s", (record_id,))
            db_conn.commit()
        finally:
            cursor.close()
        user_id = int(get_jwt_identity()) if get_jwt_identity() else None
        log_audit(user_id, "delete_history", "prediction_history", record_id, {"deleted_record": record}, request.remote_addr)
        return jsonify({"success": True, "deleted_id": record_id})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ===================== DASHBOARD =====================

@app.route("/dashboard/stats", methods=["GET"])
def dashboard_stats():
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT COUNT(*) AS total FROM prediction_history")
            total = int((cursor.fetchone() or {}).get("total", 0))
            cursor.execute("SELECT ROUND(SUM(data_length + index_length) / 1048576, 2) AS mb FROM information_schema.tables WHERE table_schema = DATABASE()")
            db_size = round(float((cursor.fetchone() or {}).get("mb", 0) or 0), 2)
            cursor.execute("SELECT COUNT(*) AS cnt FROM prediction_history WHERE DATE(COALESCE(prediction_time, created_at)) = CURDATE()")
            today = int((cursor.fetchone() or {}).get("cnt", 0))
            cursor.execute("""SELECT DATE(COALESCE(prediction_time, created_at)) AS d, COUNT(*) AS cnt
                FROM prediction_history WHERE COALESCE(prediction_time, created_at) IS NOT NULL
                GROUP BY d ORDER BY d DESC LIMIT 7""")
            daily_rows = cursor.fetchall() or []
            cursor.execute("""SELECT crop_recommendation, COUNT(*) AS cnt FROM prediction_history
                WHERE crop_recommendation IS NOT NULL AND crop_recommendation != ''
                GROUP BY crop_recommendation ORDER BY cnt DESC LIMIT 5""")
            crop_rows = cursor.fetchall() or []
            cursor.execute("SELECT AVG(predicted_yield) AS avg FROM prediction_history WHERE predicted_yield IS NOT NULL")
            avg_yield = (cursor.fetchone() or {}).get("avg")
            cursor.execute("SELECT confidence FROM prediction_history WHERE confidence IS NOT NULL")
            conf_rows = cursor.fetchall() or []
        finally:
            cursor.close()
        conf_vals = []
        for r in conf_rows:
            v = r.get("confidence")
            if v:
                t = str(v).strip().rstrip("%")
                try:
                    conf_vals.append(float(t))
                except ValueError:
                    pass
        accuracy = round(sum(conf_vals) / len(conf_vals), 2) if conf_vals else None
        crop_counts = Counter()
        for r in crop_rows:
            n = (r.get("crop_recommendation") or "").strip()
            if n:
                crop_counts[n] = int(r.get("cnt", 0))
        daily = []
        for r in reversed(daily_rows):
            dv = r.get("d")
            daily.append({"date": dv.strftime("%b %d") if isinstance(dv, datetime) else str(dv), "count": int(r.get("cnt", 0))})
        dist = [{"crop": r.get("crop_recommendation"), "count": int(r.get("cnt", 0))} for r in crop_rows]
        def rn(v): return round(float(v), 2) if v is not None else None
        return jsonify({"success": True, "stats": {
            "total_predictions": total, "most_recommended_crop": next(iter(crop_counts)) if crop_counts else None,
            "average_yield": rn(avg_yield), "prediction_accuracy": rn(accuracy),
            "database_size_mb": db_size, "today_predictions": today,
            "daily_predictions": daily, "crop_distribution": dist,
        }})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ===================== EXPORT =====================

@app.route("/export/csv", methods=["GET"])
@jwt_required()
def export_csv():
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        schema = get_history_schema(db_conn)
        cols = schema["columns"]
        order_col = schema["order_column"]
        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM prediction_history ORDER BY `{order_col}` DESC" if order_col else "SELECT * FROM prediction_history")
            rows = cursor.fetchall()
        finally:
            cursor.close()
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"agrisense_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/export/excel", methods=["GET"])
@jwt_required()
def export_excel():
    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        schema = get_history_schema(db_conn)
        order_col = schema["order_column"]
        cursor = db_conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM prediction_history ORDER BY `{order_col}` DESC" if order_col else "SELECT * FROM prediction_history")
            rows = cursor.fetchall()
        finally:
            cursor.close()
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Predictions")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"agrisense_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ===================== V2: AGRONOMY, DEVICES, TELEMETRY =====================

DEVICE_FIELDS = ["name", "crop", "sowing_date", "soil_texture", "area_m2", "irrigation_method"]


def _hash_key(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_date(value, field_name):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise agronomy.AgronomyError(f"{field_name} must be YYYY-MM-DD")


def _float_or_none(value, field_name):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise agronomy.AgronomyError(f"{field_name} must be a number")


def _device_from_request():
    """Authenticate a field device by its X-Device-Key header."""
    key = request.headers.get("X-Device-Key", "")
    if not key:
        return None, (jsonify({"success": False, "error": "X-Device-Key header required"}), 401)
    db_conn, _ = get_db()
    if db_conn is None:
        return None, (jsonify({"success": False, "error": "Database unavailable"}), 503)
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM devices WHERE api_key_hash = %s AND active = 1", (_hash_key(key),))
        device = cursor.fetchone()
    finally:
        cursor.close()
    if not device:
        return None, (jsonify({"success": False, "error": "Unknown or inactive device"}), 401)
    return device, None


@app.route("/v2/crops", methods=["GET"])
def v2_crops():
    return jsonify({
        "success": True,
        "crops": {k: {"name": c.name, "stage_days": c.stage_days, "kc": [c.kc_ini, c.kc_mid, c.kc_end], "source": c.note}
                  for k, c in agronomy.CROPS.items()},
        "soils": {k: {"name": v.name, "field_capacity": v.field_capacity, "wilting_point": v.wilting_point}
                  for k, v in agronomy.SOILS.items()},
        "irrigation_methods": sorted(agronomy.IRRIGATION_EFFICIENCY),
    })


@app.route("/v2/advise", methods=["POST"])
@jwt_required()
def v2_advise():
    """Explainable irrigation advice from explicit inputs (dashboard / manual use)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be JSON"}), 400
    try:
        missing = [f for f in ["crop", "sowing_date", "soil_texture", "area_m2"] if data.get(f) in (None, "")]
        if missing:
            raise agronomy.AgronomyError(f"Missing required fields: {', '.join(missing)}")
        weather = data.get("weather") or {}
        advice = agronomy.irrigation_advice(
            crop=data["crop"],
            sowing_date=_parse_date(data["sowing_date"], "sowing_date"),
            today=_parse_date(data["date"], "date") if data.get("date") else date.today(),
            soil_texture=data["soil_texture"],
            area_m2=_float_or_none(data["area_m2"], "area_m2"),
            irrigation_method=data.get("irrigation_method", "drip"),
            soil_vwc_pct=_float_or_none(data.get("soil_vwc_pct"), "soil_vwc_pct"),
            rain_today_mm=_float_or_none(data.get("rain_today_mm"), "rain_today_mm") or 0.0,
            rain_forecast_48h_mm=_float_or_none(data.get("rain_forecast_48h_mm"), "rain_forecast_48h_mm") or 0.0,
            weather={k: _float_or_none(v, f"weather.{k}") for k, v in weather.items()},
            latitude=_float_or_none(data.get("latitude"), "latitude"),
            elevation_m=_float_or_none(data.get("elevation_m"), "elevation_m") or 0.0,
            pump_flow_lph=_float_or_none(data.get("pump_flow_lph"), "pump_flow_lph"),
        )
    except agronomy.AgronomyError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "advice": advice.to_dict()})


@app.route("/v2/devices", methods=["POST"])
@jwt_required()
def v2_register_device():
    """Register a field node with its farm context; returns the device key ONCE."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be JSON"}), 400
    missing = [f for f in DEVICE_FIELDS if data.get(f) in (None, "")]
    if missing:
        return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400
    try:
        agronomy.get_crop(data["crop"])
        agronomy.get_soil(data["soil_texture"])
        if str(data["irrigation_method"]).lower() not in agronomy.IRRIGATION_EFFICIENCY:
            raise agronomy.AgronomyError(f"Unknown irrigation method '{data['irrigation_method']}'")
        sowing = _parse_date(data["sowing_date"], "sowing_date")
        area = _float_or_none(data["area_m2"], "area_m2")
        if area is None or area <= 0:
            raise agronomy.AgronomyError("area_m2 must be > 0")
        lat = _float_or_none(data.get("latitude"), "latitude")
        lon = _float_or_none(data.get("longitude"), "longitude")
        elev = _float_or_none(data.get("elevation_m"), "elevation_m") or 0.0
        flow = _float_or_none(data.get("pump_flow_lph"), "pump_flow_lph")
    except agronomy.AgronomyError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    db_conn, _ = get_db()
    if db_conn is None:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    device_uid = "dev_" + secrets.token_hex(6)
    device_key = secrets.token_urlsafe(32)
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """INSERT INTO devices (device_uid, api_key_hash, owner_user_id, name, crop, sowing_date, soil_texture,
               area_m2, irrigation_method, latitude, longitude, elevation_m, pump_flow_lph)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (device_uid, _hash_key(device_key), int(get_jwt_identity()), data["name"], data["crop"].lower(),
             sowing, data["soil_texture"].lower(), area, data["irrigation_method"].lower(), lat, lon, elev, flow),
        )
        db_conn.commit()
    except Exception as exc:
        logger.error("Device registration failed: %s", exc)
        return jsonify({"success": False, "error": "Could not register device"}), 500
    finally:
        cursor.close()
    log_audit(int(get_jwt_identity()), "register_device", "device", None, {"device_uid": device_uid}, request.remote_addr)
    return jsonify({
        "success": True, "device_uid": device_uid, "device_key": device_key,
        "note": "Store device_key in the node's setup portal now; it is not shown again.",
    }), 201


@app.route("/v2/telemetry", methods=["POST"])
def v2_telemetry():
    """Field node posts readings; receives an irrigation command in response."""
    device, error = _device_from_request()
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Request body must be JSON"}), 400
    try:
        soil_vwc = _float_or_none(data.get("soil_vwc_pct"), "soil_vwc_pct")
        if soil_vwc is not None and not (0 <= soil_vwc <= 100):
            raise agronomy.AgronomyError("soil_vwc_pct must be 0-100")
        air_t = _float_or_none(data.get("air_temp_c"), "air_temp_c")
        air_rh = _float_or_none(data.get("air_rh_pct"), "air_rh_pct")
        rain_mm = _float_or_none(data.get("rain_mm"), "rain_mm") or 0.0
        battery = _float_or_none(data.get("battery_v"), "battery_v")
    except agronomy.AgronomyError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    db_conn, _ = get_db()
    cursor = db_conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """INSERT INTO sensor_readings (device_id, soil_vwc_pct, air_temp_c, air_rh_pct, rain_mm, battery_v, firmware)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (device["id"], soil_vwc, air_t, air_rh, rain_mm, battery, str(data.get("firmware", ""))[:20]),
        )
        db_conn.commit()
    except Exception as exc:
        logger.warning("Reading not stored: %s", exc)
    finally:
        cursor.close()

    forecast = fetch_forecast_summary(
        float(device["latitude"]) if device.get("latitude") is not None else None,
        float(device["longitude"]) if device.get("longitude") is not None else None,
        OWM_API_KEY,
    )
    weather = {}
    if forecast:
        weather = {k: forecast[k] for k in ["t_max", "t_min", "rh_max", "rh_min", "wind_u2"] if forecast.get(k) is not None}
    try:
        sowing = device["sowing_date"]
        if isinstance(sowing, str):
            sowing = _parse_date(sowing, "sowing_date")
        advice = agronomy.irrigation_advice(
            crop=device["crop"], sowing_date=sowing, today=date.today(),
            soil_texture=device["soil_texture"], area_m2=float(device["area_m2"]),
            irrigation_method=device["irrigation_method"], soil_vwc_pct=soil_vwc,
            rain_today_mm=rain_mm,
            rain_forecast_48h_mm=forecast["rain_forecast_48h_mm"] if forecast else 0.0,
            weather=weather,
            latitude=float(device["latitude"]) if device.get("latitude") is not None else None,
            elevation_m=float(device.get("elevation_m") or 0.0),
            pump_flow_lph=float(device["pump_flow_lph"]) if device.get("pump_flow_lph") else None,
        )
    except agronomy.AgronomyError as exc:
        return jsonify({"success": False, "error": str(exc), "command": {"irrigate": False, "minutes": 0}}), 422

    result = advice.to_dict()
    if not forecast:
        result["reasons"].append("Weather forecast unavailable: decision based on soil moisture only.")
    return jsonify({
        "success": True,
        "device_uid": device["device_uid"],
        "command": {"irrigate": advice.irrigate, "minutes": advice.minutes or 0, "litres": advice.litres},
        "advice": result,
        "weather": forecast,
    })


if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)
