import io
import json
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pandas as pd

from app import app

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, ".."))

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

COLUMN_DEFS = [
    {"Field": "id", "Key": "PRI"},
    {"Field": "region", "Key": ""},
    {"Field": "crop_type", "Key": ""},
    {"Field": "soil_moisture", "Key": ""},
    {"Field": "soil_ph", "Key": ""},
    {"Field": "temperature", "Key": ""},
    {"Field": "rainfall", "Key": ""},
    {"Field": "humidity", "Key": ""},
    {"Field": "sunlight_hours", "Key": ""},
    {"Field": "irrigation_type", "Key": ""},
    {"Field": "fertilizer_type", "Key": ""},
    {"Field": "pesticide_usage", "Key": ""},
    {"Field": "total_days", "Key": ""},
    {"Field": "latitude", "Key": ""},
    {"Field": "longitude", "Key": ""},
    {"Field": "ndvi_index", "Key": ""},
    {"Field": "crop_recommendation", "Key": ""},
    {"Field": "predicted_yield", "Key": ""},
    {"Field": "disease_prediction", "Key": ""},
    {"Field": "heat_stress", "Key": ""},
    {"Field": "soil_health", "Key": ""},
    {"Field": "fertilizer_recommendation", "Key": ""},
    {"Field": "irrigation_time", "Key": ""},
    {"Field": "rain_impact", "Key": ""},
    {"Field": "farm_efficiency", "Key": ""},
    {"Field": "confidence", "Key": ""},
    {"Field": "model_version", "Key": ""},
    {"Field": "prediction_time", "Key": ""},
    {"Field": "created_at", "Key": ""},
]

SAMPLE_ROWS = [
    {"id": 1, "region": "North India", "crop_type": "Rice", "prediction_time": datetime(2025, 1, 1)},
    {"id": 2, "region": "South India", "crop_type": "Wheat", "prediction_time": datetime(2025, 1, 2)},
]


def make_query_cursor():
    """Return a cursor whose execute() dynamically sets fetchone/fetchall based on query."""
    cursor = MagicMock()
    cursor.dictionary = True
    cursor.lastrowid = 1

    def lazy_execute(sql, params=None):
        s = sql.strip().upper() if sql else ""
        if "SHOW COLUMNS" in s:
            cursor.fetchall.return_value = COLUMN_DEFS
            cursor.fetchone.return_value = None
        elif "COUNT(*)" in s:
            cursor.fetchone.return_value = {"total": 5}
            cursor.fetchall.return_value = []
        elif "SELECT DISTINCT" in s:
            if "REGION" in s:
                cursor.fetchall.return_value = [{"v": "North India"}, {"v": "South India"}]
            elif "CROP_TYPE" in s:
                cursor.fetchall.return_value = [{"v": "Rice"}, {"v": "Wheat"}]
            elif "CROP_RECOMMENDATION" in s:
                cursor.fetchall.return_value = [{"v": "Rice"}]
            elif "DISEASE_PREDICTION" in s:
                cursor.fetchall.return_value = [{"v": "Healthy"}, {"v": "Blight"}]
            else:
                cursor.fetchall.return_value = []
            cursor.fetchone.return_value = None
        elif "MIN(" in s and "MAX(" in s:
            cursor.fetchone.return_value = {"mn": datetime(2025, 1, 1), "mx": datetime(2025, 12, 31)}
            cursor.fetchall.return_value = []
        elif "INFORMATION_SCHEMA" in s:
            cursor.fetchone.return_value = {"mb": 5.2}
            cursor.fetchall.return_value = []
        elif "CURDATE()" in s:
            cursor.fetchone.return_value = {"cnt": 10}
            cursor.fetchall.return_value = []
        elif "GROUP BY D" in s or "GROUP BY  D" in s:
            cursor.fetchall.return_value = [
                {"d": datetime(2025, 6, 1), "cnt": 5},
                {"d": datetime(2025, 6, 2), "cnt": 3},
            ]
            cursor.fetchone.return_value = None
        elif "GROUP BY CROP_RECOMMENDATION" in s:
            cursor.fetchall.return_value = [
                {"crop_recommendation": "Rice", "cnt": 50},
                {"crop_recommendation": "Wheat", "cnt": 30},
            ]
            cursor.fetchone.return_value = None
        elif "AVG(" in s:
            cursor.fetchone.return_value = {"avg": 4500.0}
            cursor.fetchall.return_value = []
        elif "CONFIDENCE" in s and "IS NOT NULL" in s:
            cursor.fetchall.return_value = [{"confidence": "85%"}, {"confidence": "90%"}]
            cursor.fetchone.return_value = None
        elif "SELECT *" in s and "WHERE" not in s:
            cursor.fetchall.return_value = SAMPLE_ROWS
            cursor.fetchone.return_value = SAMPLE_ROWS[0] if SAMPLE_ROWS else None
        elif "SELECT *" in s and "WHERE" in s:
            cursor.fetchall.return_value = SAMPLE_ROWS
            cursor.fetchone.return_value = SAMPLE_ROWS[0] if SAMPLE_ROWS else None
        elif "INSERT INTO USERS" in s:
            cursor.lastrowid = 1
        elif "INSERT INTO USER_SETTINGS" in s:
            pass
        elif "INSERT INTO PREDICTION_HISTORY" in s:
            pass
        elif "DELETE" in s:
            pass
        elif s.startswith("SELECT ID") and "FROM USERS" in s and "WHERE USERNAME" in s:
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
        elif "WHERE ID =" in s and "FROM USERS" in s:
            cursor.fetchone.return_value = {"id": 1, "username": "testuser", "email": "test@example.com", "role": "user", "created_at": datetime(2025, 1, 1)}
            cursor.fetchall.return_value = []
        elif "WHERE USERNAME =" in s and "FROM USERS" in s:
            cursor.fetchone.return_value = {
                "id": 1, "username": "testuser", "email": "test@example.com",
                "password_hash": "hash", "role": "user",
            }
            cursor.fetchall.return_value = []
        else:
            cursor.fetchone.return_value = {}
            cursor.fetchall.return_value = []

    cursor.execute.side_effect = lazy_execute
    return cursor


def mock_db_ok(cursor=None):
    if cursor is None:
        cursor = make_query_cursor()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def mock_db_unavail():
    return None, None


def single_encoder():
    enc = MagicMock()
    enc.transform.return_value = [0]
    enc.inverse_transform.return_value = ["Normal"]
    enc.classes_ = ["valid"]
    return enc


# =============================================================================
# HEALTH
# =============================================================================
class TestHealthEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_health_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")
        self.assertIn("models_loaded", data)

    @patch("app.get_db")
    def test_health_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["database"], "unavailable")

    def test_health_wrong_method(self):
        resp = self.client.post("/health")
        self.assertEqual(resp.status_code, 405)


# =============================================================================
# AUTH - REGISTER
# =============================================================================
class TestAuthRegister(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_register_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/auth/register", json={
            "username": "testuser", "email": "test@example.com", "password": "password123",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.get_json()["success"])
        self.assertEqual(resp.get_json()["user_id"], 1)

    def test_register_empty_json(self):
        resp = self.client.post("/auth/register", json={})
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_fields(self):
        resp = self.client.post("/auth/register", json={"username": "test"})
        self.assertEqual(resp.status_code, 400)

    def test_register_short_password(self):
        resp = self.client.post("/auth/register", json={
            "username": "u", "email": "e@e.com", "password": "12345",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at least 6 characters", resp.get_json()["error"])

    def test_register_empty_fields(self):
        resp = self.client.post("/auth/register", json={"username": "", "email": "", "password": ""})
        self.assertEqual(resp.status_code, 400)

    @patch("app.get_db")
    def test_register_duplicate(self, mock_db):
        cursor = make_query_cursor()
        def dup_execute(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = {"id": 1}
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = dup_execute
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.post("/auth/register", json={
            "username": "existing", "email": "existing@example.com", "password": "password123",
        })
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.get_json()["error"])

    @patch("app.get_db")
    def test_register_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        resp = self.client.post("/auth/register", json={
            "username": "u", "email": "e@e.com", "password": "password123",
        })
        self.assertEqual(resp.status_code, 503)

    @patch("app.get_db")
    def test_register_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB connection lost")
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.post("/auth/register", json={
            "username": "u", "email": "e@e.com", "password": "password123",
        })
        self.assertEqual(resp.status_code, 500)

    def test_register_wrong_method(self):
        resp = self.client.get("/auth/register")
        self.assertEqual(resp.status_code, 405)

    def test_register_non_json(self):
        resp = self.client.post("/auth/register", data="not-json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)


# =============================================================================
# AUTH - LOGIN
# =============================================================================
class TestAuthLogin(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    @patch("app.bcrypt.check_password_hash")
    def test_login_success(self, mock_check, mock_db):
        mock_check.return_value = True
        cursor = make_query_cursor()
        def user_execute(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = {
                    "id": 1, "username": "testuser", "email": "test@example.com",
                    "password_hash": "hash", "role": "user",
                }
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = user_execute
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.post("/auth/login", json={"username": "testuser", "password": "password123"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertEqual(data["user"]["id"], 1)

    def test_login_empty_json(self):
        resp = self.client.post("/auth/login", json={})
        self.assertEqual(resp.status_code, 400)

    @patch("app.get_db")
    def test_login_missing_username(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/auth/login", json={"password": "pwd"})
        # Login does not validate empty username before calling DB;
        # it queries with empty username, finds no user, and returns 401.
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid credentials", resp.get_json()["error"])

    @patch("app.get_db")
    def test_login_invalid_credentials(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/auth/login", json={"username": "unknown", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)

    @patch("app.get_db")
    def test_login_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        resp = self.client.post("/auth/login", json={"username": "u", "password": "p"})
        self.assertEqual(resp.status_code, 503)

    @patch("app.get_db")
    def test_login_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.post("/auth/login", json={"username": "u", "password": "p"})
        self.assertEqual(resp.status_code, 500)


# =============================================================================
# AUTH - ME
# =============================================================================
class TestAuthMe(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _get_token(self):
        cursor = make_query_cursor()
        def user_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = {
                    "id": 1, "username": "testuser", "email": "test@example.com",
                    "password_hash": "hash", "role": "user",
                }
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = user_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor)):
            with patch("app.bcrypt.check_password_hash", return_value=True):
                return self.client.post("/auth/login", json={
                    "username": "testuser", "password": "password123",
                }).get_json()["token"]

    def test_auth_me_no_token(self):
        resp = self.client.get("/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_auth_me_invalid_token(self):
        resp = self.client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        self.assertEqual(resp.status_code, 422)

    @patch("app.get_db")
    def test_auth_me_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        token = self._get_token()
        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["username"], "testuser")

    @patch("app.get_db")
    def test_auth_me_user_not_found(self, mock_db):
        token = self._get_token()
        cursor = make_query_cursor()
        def notfound_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = None
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = notfound_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 404)

    @patch("app.get_db")
    def test_auth_me_db_unavailable(self, mock_db):
        token = self._get_token()
        mock_db.return_value = mock_db_unavail()
        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 503)

    @patch("app.get_db")
    def test_auth_me_db_error(self, mock_db):
        token = self._get_token()
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 500)

    @patch("app.get_db")
    def test_auth_me_wrong_method(self, mock_db):
        token = self._get_token()
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 405)


# =============================================================================
# WEATHER
# =============================================================================
class TestWeatherEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.key_patcher = patch("app.OWM_API_KEY", "test_api_key_12345")
        self.key_patcher.start()

    def tearDown(self):
        self.key_patcher.stop()

    @patch("app.requests.get")
    def test_weather_current_success(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"main": {"temp": 28.5}})
        resp = self.client.get("/weather/current?lat=28.61&lon=77.23")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("main", resp.get_json())

    def test_weather_current_missing_params(self):
        resp = self.client.get("/weather/current")
        self.assertEqual(resp.status_code, 400)

    def test_weather_current_missing_lat(self):
        resp = self.client.get("/weather/current?lon=77.23")
        self.assertEqual(resp.status_code, 400)

    def test_weather_current_missing_lon(self):
        resp = self.client.get("/weather/current?lat=28.61")
        self.assertEqual(resp.status_code, 400)

    def test_weather_current_no_api_key(self):
        with patch("app.OWM_API_KEY", ""):
            resp = self.client.get("/weather/current?lat=28.61&lon=77.23")
            self.assertEqual(resp.status_code, 503)
            self.assertIn("API key not configured", resp.get_json()["error"])

    @patch("app.requests.get")
    def test_weather_current_api_error(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")
        with patch("app.OWM_API_KEY", "key"):
            resp = self.client.get("/weather/current?lat=28.61&lon=77.23")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("Connection timeout", resp.get_json()["error"])

    @patch("app.requests.get")
    def test_weather_forecast_success(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"list": []})
        resp = self.client.get("/weather/forecast?lat=28.61&lon=77.23")
        self.assertEqual(resp.status_code, 200)

    def test_weather_forecast_missing_params(self):
        resp = self.client.get("/weather/forecast")
        self.assertEqual(resp.status_code, 400)

    def test_weather_forecast_no_api_key(self):
        with patch("app.OWM_API_KEY", ""):
            resp = self.client.get("/weather/forecast?lat=28.61&lon=77.23")
            self.assertEqual(resp.status_code, 503)

    @patch("app.requests.get")
    def test_weather_forecast_api_error(self, mock_get):
        mock_get.side_effect = Exception("API unavailable")
        with patch("app.OWM_API_KEY", "key"):
            resp = self.client.get("/weather/forecast?lat=28.61&lon=77.23")
            self.assertEqual(resp.status_code, 502)


# =============================================================================
# PREDICT
# =============================================================================
class TestPredictEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.enc = single_encoder()

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_full_success(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/predict", json=VALID_PAYLOAD)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        p = data["prediction"]
        for key in ["Irrigation", "PredictedYield(Kg/Hectare)", "Disease", "HeatStress",
                     "SoilHealth", "Fertilizer", "IrrigationTime", "RainImpact",
                     "FarmEfficiency", "CropRecommendation", "PredictionTime",
                     "ModelVersion", "Confidence"]:
            self.assertIn(key, p)
        self.assertEqual(p["ModelVersion"], "v1.0")

    def test_predict_no_body(self):
        resp = self.client.post("/predict", data="{}", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_predict_empty_body(self):
        resp = self.client.post("/predict", json={})
        self.assertEqual(resp.status_code, 400)

    def test_predict_missing_field(self):
        incomplete = {k: v for k, v in VALID_PAYLOAD.items() if k != "region"}
        resp = self.client.post("/predict", json=incomplete)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing required fields", resp.get_json()["error"])

    @patch("app.encoders")
    def test_predict_invalid_encoder(self, mock_enc):
        bad_enc = MagicMock()
        bad_enc.transform.side_effect = ValueError("invalid")
        bad_enc.classes_ = ["valid1", "valid2"]
        mock_enc.__getitem__.return_value = bad_enc
        resp = self.client.post("/predict", json=VALID_PAYLOAD)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid", resp.get_json()["error"])

    def test_predict_wrong_method(self):
        resp = self.client.get("/predict")
        self.assertEqual(resp.status_code, 405)

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_db_save_failure_still_returns_prediction(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB write failed")
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.post("/predict", json=VALID_PAYLOAD)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_confidence(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        # mock compute_confidence to return a known value
        with patch("app.compute_confidence", return_value="85.0%"):
            mock_db.return_value = mock_db_ok()
            resp = self.client.post("/predict", json=VALID_PAYLOAD)
            self.assertEqual(resp.get_json()["prediction"]["Confidence"], "85.0%")

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_irrigation_decision(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_irr.predict.return_value = [1]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        mock_db.return_value = mock_db_ok()
        self.assertEqual(
            self.client.post("/predict", json=VALID_PAYLOAD).get_json()["prediction"]["Irrigation"],
            "Start Irrigation",
        )
        mock_irr.predict.return_value = [0]
        self.assertEqual(
            self.client.post("/predict", json=VALID_PAYLOAD).get_json()["prediction"]["Irrigation"],
            "No Irrigation Needed",
        )

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_all_fields_boundaries(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        mock_db.return_value = mock_db_ok()
        extremes = dict(VALID_PAYLOAD, soil_moisture_=0, soil_pH=14, temperature_C=50,
                        rainfall_mm=0, humidity_=100, sunlight_hours=24, pesticide_usage_ml=0,
                        total_days=1, NDVI_index=0, latitude=-90, longitude=-180)
        resp = self.client.post("/predict", json=extremes)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    @patch("app.get_db")
    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_category_outputs(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop, mock_db,
    ):
        mock_enc.__getitem__.return_value = self.enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []
        mock_db.return_value = mock_db_ok()
        resp = self.client.post("/predict", json=VALID_PAYLOAD)
        p = resp.get_json()["prediction"]
        self.assertIsInstance(p["PredictedYield(Kg/Hectare)"], (int, float))
        self.assertIsInstance(p["Irrigation"], str)
        self.assertIsInstance(p["Disease"], str)
        self.assertIsInstance(p["ModelVersion"], str)
        self.assertIsInstance(p["PredictionTime"], str)


# =============================================================================
# HISTORY - META
# =============================================================================
class TestHistoryMeta(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_meta_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history/meta")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("regions", data)
        self.assertIn("crops", data)
        self.assertIn("recommended_crops", data)
        self.assertIn("diseases", data)
        self.assertIn("date_range", data)
        self.assertIsInstance(data["regions"], list)

    @patch("app.get_db")
    def test_meta_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.get("/history/meta").status_code, 503)

    @patch("app.get_db")
    def test_meta_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.get("/history/meta").status_code, 500)


# =============================================================================
# HISTORY - LIST
# =============================================================================
class TestHistoryList(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_list_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("pagination", data)
        self.assertEqual(data["pagination"]["total"], 5)

    @patch("app.get_db")
    def test_list_with_filters(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history?page=1&per_page=5&region=South+India&search=Rice")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    @patch("app.get_db")
    def test_list_invalid_page(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history?page=-1")
        self.assertEqual(resp.status_code, 200)

    @patch("app.get_db")
    def test_list_invalid_per_page(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history?per_page=999")
        self.assertEqual(resp.status_code, 200)

    @patch("app.get_db")
    def test_list_sorting(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/history?sort=region&order=ASC")
        self.assertEqual(resp.status_code, 200)

    @patch("app.get_db")
    def test_list_pagination_structure(self, mock_db):
        mock_db.return_value = mock_db_ok()
        data = self.client.get("/history?page=1&per_page=10").get_json()
        pag = data["pagination"]
        for key in ["page", "per_page", "total", "total_pages"]:
            self.assertIn(key, pag)

    @patch("app.get_db")
    def test_list_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.get("/history").status_code, 503)

    @patch("app.get_db")
    def test_list_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.get("/history").status_code, 500)


# =============================================================================
# HISTORY - DELETE
# =============================================================================
class TestHistoryDelete(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_delete_success(self, mock_db):
        cursor = make_query_cursor()
        def del_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SHOW COLUMNS" in s:
                cursor.fetchall.return_value = COLUMN_DEFS
                cursor.fetchone.return_value = None
            elif "SELECT *" in s:
                cursor.fetchone.return_value = {"id": 1, "region": "Test"}
                cursor.fetchall.return_value = []
            elif "DELETE" in s:
                pass
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = del_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.delete("/history/1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        self.assertEqual(resp.get_json()["deleted_id"], 1)

    @patch("app.get_db")
    def test_delete_not_found(self, mock_db):
        cursor = make_query_cursor()
        def nf_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SHOW COLUMNS" in s:
                cursor.fetchall.return_value = COLUMN_DEFS
                cursor.fetchone.return_value = None
            elif "SELECT *" in s:
                cursor.fetchone.return_value = None
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = nf_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.delete("/history/99999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Record not found", resp.get_json()["error"])

    @patch("app.get_db")
    def test_delete_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.delete("/history/1").status_code, 503)

    @patch("app.get_db")
    def test_delete_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.delete("/history/1").status_code, 500)


# =============================================================================
# DASHBOARD STATS
# =============================================================================
class TestDashboardStats(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_stats_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/dashboard/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        s = data["stats"]
        for key in ["total_predictions", "average_yield", "database_size_mb",
                     "today_predictions", "daily_predictions", "crop_distribution",
                     "prediction_accuracy", "most_recommended_crop"]:
            self.assertIn(key, s)
        self.assertEqual(s["total_predictions"], 5)
        self.assertEqual(s["database_size_mb"], 5.2)

    @patch("app.get_db")
    def test_stats_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.get("/dashboard/stats").status_code, 503)

    @patch("app.get_db")
    def test_stats_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.get("/dashboard/stats").status_code, 500)

    @patch("app.get_db")
    def test_stats_empty_data(self, mock_db):
        cursor = make_query_cursor()
        def empty_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "COUNT(*)" in s and "TOTAL" in s:
                cursor.fetchone.return_value = {"total": 0}
            elif "INFORMATION_SCHEMA" in s:
                cursor.fetchone.return_value = {"mb": 0}
            elif "CURDATE()" in s:
                cursor.fetchone.return_value = {"cnt": 0}
            elif "AVG(" in s:
                cursor.fetchone.return_value = {"avg": None}
            elif "CONFIDENCE" in s and "IS NOT NULL" in s:
                cursor.fetchall.return_value = []
            elif "GROUP BY" in s:
                cursor.fetchall.return_value = []
            elif "GROUP BY D" in s:
                cursor.fetchall.return_value = []
            else:
                cursor.fetchone.return_value = {}
                cursor.fetchall.return_value = []
        cursor.execute.side_effect = empty_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.get("/dashboard/stats")
        self.assertEqual(resp.status_code, 200)
        s = resp.get_json()["stats"]
        self.assertEqual(s["total_predictions"], 0)
        self.assertIsNone(s["average_yield"])
        self.assertIsNone(s["prediction_accuracy"])
        self.assertIsNone(s["most_recommended_crop"])


# =============================================================================
# EXPORT CSV
# =============================================================================
class TestExportCSV(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_export_csv_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/csv")
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))

    @patch("app.get_db")
    def test_export_csv_empty(self, mock_db):
        cursor = make_query_cursor()
        def empty_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SHOW COLUMNS" in s:
                cursor.fetchall.return_value = COLUMN_DEFS
            elif "SELECT *" in s:
                cursor.fetchall.return_value = []
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = empty_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.get("/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.mimetype)

    @patch("app.get_db")
    def test_export_csv_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.get("/export/csv").status_code, 503)

    @patch("app.get_db")
    def test_export_csv_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.get("/export/csv").status_code, 500)


# =============================================================================
# EXPORT EXCEL
# =============================================================================
class TestExportExcel(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.get_db")
    def test_export_excel_success(self, mock_db):
        mock_db.return_value = mock_db_ok()
        resp = self.client.get("/export/excel")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheet", resp.mimetype)
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))

    @patch("app.get_db")
    def test_export_excel_empty(self, mock_db):
        cursor = make_query_cursor()
        def empty_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SHOW COLUMNS" in s:
                cursor.fetchall.return_value = COLUMN_DEFS
            elif "SELECT *" in s:
                cursor.fetchall.return_value = []
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = empty_exec
        mock_db.return_value = mock_db_ok(cursor)
        resp = self.client.get("/export/excel")
        self.assertEqual(resp.status_code, 200)

    @patch("app.get_db")
    def test_export_excel_db_unavailable(self, mock_db):
        mock_db.return_value = mock_db_unavail()
        self.assertEqual(self.client.get("/export/excel").status_code, 503)

    @patch("app.get_db")
    def test_export_excel_db_error(self, mock_db):
        cursor = make_query_cursor()
        cursor.execute.side_effect = Exception("DB error")
        mock_db.return_value = mock_db_ok(cursor)
        self.assertEqual(self.client.get("/export/excel").status_code, 500)


# =============================================================================
# DATABASE CONNECTION LOSS (all endpoints)
# =============================================================================
class TestDatabaseConnectionLoss(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _assert_503(self, method, path, body=None):
        with patch("app.get_db", return_value=mock_db_unavail()):
            if method == "GET":
                resp = self.client.get(path)
            elif method == "POST":
                resp = self.client.post(path, json=body or {})
            elif method == "DELETE":
                resp = self.client.delete(path)
            else:
                self.fail(f"Bad method {method}")
            self.assertEqual(resp.status_code, 503)
            self.assertIn("Database unavailable", resp.get_json().get("error", ""))

    def test_history_endpoints(self):
        self._assert_503("GET", "/history/meta")
        self._assert_503("GET", "/history")
        self._assert_503("DELETE", "/history/1")

    def test_dashboard_endpoints(self):
        self._assert_503("GET", "/dashboard/stats")

    def test_export_endpoints(self):
        self._assert_503("GET", "/export/csv")
        self._assert_503("GET", "/export/excel")

    def test_auth_endpoints(self):
        self._assert_503("POST", "/auth/register", {"username": "u", "email": "e@e.com", "password": "123456"})
        self._assert_503("POST", "/auth/login", {"username": "u", "password": "p"})

    def test_auth_me(self):
        cursor = make_query_cursor()
        def user_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = {
                    "id": 1, "username": "t", "email": "t@t.com",
                    "password_hash": "hash", "role": "user",
                }
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = user_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor)):
            with patch("app.bcrypt.check_password_hash", return_value=True):
                token = self.client.post("/auth/login", json={
                    "username": "t", "password": "p",
                }).get_json()["token"]
        with patch("app.get_db", return_value=mock_db_unavail()):
            resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resp.status_code, 503)


# =============================================================================
# FUNCTIONAL FLOW (end-to-end like)
# =============================================================================
class TestFunctionalFlow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_register_login_profile_flow(self):
        cursor = make_query_cursor()
        def reg_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor.fetchone.return_value = None
            elif "INSERT INTO USERS" in s:
                cursor.lastrowid = 1
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = reg_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor)):
            resp = self.client.post("/auth/register", json={
                "username": "farmer1", "email": "farmer1@farm.com", "password": "secure123",
            })
            self.assertEqual(resp.status_code, 201)

        cursor2 = make_query_cursor()
        def login_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor2.fetchone.return_value = {
                    "id": 1, "username": "farmer1", "email": "farmer1@farm.com",
                    "password_hash": "hash", "role": "user",
                }
            else:
                cursor2.fetchone.return_value = {}
        cursor2.execute.side_effect = login_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor2)):
            with patch("app.bcrypt.check_password_hash", return_value=True):
                resp = self.client.post("/auth/login", json={
                    "username": "farmer1", "password": "secure123",
                })
                self.assertEqual(resp.status_code, 200)
                token = resp.get_json()["token"]

        cursor3 = make_query_cursor()
        def me_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SELECT ID" in s:
                cursor3.fetchone.return_value = {
                    "id": 1, "username": "farmer1", "email": "farmer1@farm.com",
                    "role": "user", "created_at": datetime(2025, 1, 1),
                }
            else:
                cursor3.fetchone.return_value = {}
        cursor3.execute.side_effect = me_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor3)):
            resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["user"]["username"], "farmer1")

    def test_history_export_delete_flow(self):
        with patch("app.get_db", return_value=mock_db_ok()):
            resp = self.client.get("/history")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(resp.get_json()["data"]), 2)

            resp = self.client.get("/export/csv")
            self.assertEqual(resp.status_code, 200)

            resp = self.client.get("/export/excel")
            self.assertEqual(resp.status_code, 200)

        cursor = make_query_cursor()
        def del_exec(sql, params=None):
            s = sql.strip().upper() if sql else ""
            if "SHOW COLUMNS" in s:
                cursor.fetchall.return_value = COLUMN_DEFS
                cursor.fetchone.return_value = None
            elif "SELECT *" in s:
                cursor.fetchone.return_value = {"id": 1, "region": "Test"}
                cursor.fetchall.return_value = []
            else:
                cursor.fetchone.return_value = {}
        cursor.execute.side_effect = del_exec
        with patch("app.get_db", return_value=mock_db_ok(cursor)):
            resp = self.client.delete("/history/1")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json()["success"])

    @patch("app.crop_model")
    @patch("app.farm_model")
    @patch("app.rain_model")
    @patch("app.time_model")
    @patch("app.fertilizer_model")
    @patch("app.soil_model")
    @patch("app.heat_model")
    @patch("app.yield_model")
    @patch("app.disease_model")
    @patch("app.irrigation_model")
    @patch("app.encoders")
    def test_predict_and_check_history(
        self, mock_enc, mock_irr, mock_dis, mock_yd, mock_heat, mock_soil,
        mock_fert, mock_time, mock_rain, mock_farm, mock_crop,
    ):
        enc = single_encoder()
        mock_enc.__getitem__.return_value = enc
        for m in [mock_irr, mock_dis, mock_heat, mock_soil, mock_fert, mock_time, mock_rain, mock_farm, mock_crop]:
            m.predict.return_value = [0]
        mock_yd.predict.return_value = [4500.0]
        mock_yd.feature_names_in_ = []

        with patch("app.get_db", return_value=mock_db_ok()):
            resp = self.client.post("/predict", json=VALID_PAYLOAD)
            self.assertEqual(resp.status_code, 200)
            p = resp.get_json()["prediction"]
            self.assertEqual(p["ModelVersion"], "v1.0")
            self.assertIsNotNone(p["PredictionTime"])

            resp = self.client.get("/history")
            self.assertEqual(resp.status_code, 200)

            resp = self.client.get("/dashboard/stats")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("total_predictions", resp.get_json()["stats"])


# =============================================================================
# CROSS-CUTTING: SERVER ERRORS
# =============================================================================
class TestServerErrors(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_404_unknown_route(self):
        resp = self.client.get("/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_405_wrong_method_history_delete(self):
        resp = self.client.get("/history/1")
        self.assertEqual(resp.status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
