"""Tests for the v2 advise, device-registration and telemetry endpoints."""

import hashlib
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token

from app import app


def auth_headers(user_id="7"):
    with app.app_context():
        return {"Authorization": f"Bearer {create_access_token(identity=user_id)}"}


def db_with(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


DEVICE_KEY = "test-device-key"
DEVICE_ROW = {
    "id": 3, "device_uid": "dev_abc123", "crop": "onion", "sowing_date": date(2026, 1, 1),
    "soil_texture": "clay", "area_m2": 1000, "irrigation_method": "drip",
    "latitude": 17.66, "longitude": 75.9, "elevation_m": 457, "pump_flow_lph": 1000, "active": 1,
}

ADVISE_BODY = {
    "crop": "onion", "sowing_date": "2026-01-01", "date": "2026-02-20", "soil_texture": "clay",
    "area_m2": 1000, "irrigation_method": "drip", "soil_vwc_pct": 25,
    "weather": {"t_max": 34, "t_min": 18, "rh_mean": 45}, "latitude": 17.66, "pump_flow_lph": 1000,
}


class TestAdvise(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_requires_token(self):
        self.assertEqual(self.client.post("/v2/advise", json=ADVISE_BODY).status_code, 401)

    def test_success(self):
        r = self.client.post("/v2/advise", json=ADVISE_BODY, headers=auth_headers())
        self.assertEqual(r.status_code, 200)
        advice = r.get_json()["advice"]
        self.assertTrue(advice["irrigate"])
        self.assertGreater(advice["litres"], 0)
        self.assertTrue(advice["reasons"])

    def test_bad_input(self):
        for body in [{**ADVISE_BODY, "crop": "banana"}, {**ADVISE_BODY, "sowing_date": "01/01/2026"},
                     {k: v for k, v in ADVISE_BODY.items() if k != "area_m2"}, {**ADVISE_BODY, "area_m2": "big"}]:
            r = self.client.post("/v2/advise", json=body, headers=auth_headers())
            self.assertEqual(r.status_code, 400, body)

    def test_crops_catalogue(self):
        r = self.client.get("/v2/crops")
        self.assertIn("pomegranate", r.get_json()["crops"])


class TestDeviceRegistration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.body = {"name": "Plot 2", "crop": "pomegranate", "sowing_date": "2026-06-01",
                     "soil_texture": "clay", "area_m2": 4047, "irrigation_method": "drip",
                     "latitude": 17.66, "longitude": 75.9, "pump_flow_lph": 2000}

    def test_requires_token(self):
        self.assertEqual(self.client.post("/v2/devices", json=self.body).status_code, 401)

    @patch("app.get_db")
    def test_register_returns_key_once_and_stores_hash(self, mock_db):
        mock_db.return_value = db_with(MagicMock())
        r = self.client.post("/v2/devices", json=self.body, headers=auth_headers())
        self.assertEqual(r.status_code, 201)
        key = r.get_json()["device_key"]
        insert_args = mock_db.return_value[1].execute.call_args_list[0][0][1]
        self.assertEqual(insert_args[1], hashlib.sha256(key.encode()).hexdigest())
        self.assertNotIn(key, insert_args)

    def test_validation(self):
        r = self.client.post("/v2/devices", json={**self.body, "crop": "Auto"}, headers=auth_headers())
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/v2/devices", json={"name": "x"}, headers=auth_headers())
        self.assertEqual(r.status_code, 400)

    @patch("app.get_db", return_value=(None, None))
    def test_db_unavailable(self, _):
        r = self.client.post("/v2/devices", json=self.body, headers=auth_headers())
        self.assertEqual(r.status_code, 503)


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_requires_device_key(self):
        self.assertEqual(self.client.post("/v2/telemetry", json={}).status_code, 401)

    @patch("app.get_db")
    def test_unknown_device(self, mock_db):
        cur = MagicMock()
        cur.fetchone.return_value = None
        mock_db.return_value = db_with(cur)
        r = self.client.post("/v2/telemetry", json={}, headers={"X-Device-Key": "nope"})
        self.assertEqual(r.status_code, 401)

    @patch("app.fetch_forecast_summary", return_value=None)
    @patch("app.get_db")
    def test_dry_soil_returns_pump_command(self, mock_db, _):
        cur = MagicMock()
        cur.fetchone.return_value = DEVICE_ROW
        mock_db.return_value = db_with(cur)
        r = self.client.post("/v2/telemetry", json={"soil_vwc_pct": 24, "air_temp_c": 31},
                             headers={"X-Device-Key": DEVICE_KEY})
        self.assertEqual(r.status_code, 200)
        cmd = r.get_json()["command"]
        self.assertTrue(cmd["irrigate"])
        self.assertGreater(cmd["minutes"], 0)
        lookup_hash = cur.execute.call_args_list[0][0][1][0]
        self.assertEqual(lookup_hash, hashlib.sha256(DEVICE_KEY.encode()).hexdigest())
        self.assertTrue(any("forecast unavailable" in x for x in r.get_json()["advice"]["reasons"]))

    @patch("app.fetch_forecast_summary", return_value={
        "t_max": 33, "t_min": 20, "rh_max": 80, "rh_min": 40, "wind_u2": 2.0,
        "rain_next_24h_mm": 30, "rain_forecast_48h_mm": 70, "source": "test"})
    @patch("app.get_db")
    def test_forecast_rain_holds_pump(self, mock_db, _):
        cur = MagicMock()
        cur.fetchone.return_value = DEVICE_ROW
        mock_db.return_value = db_with(cur)
        r = self.client.post("/v2/telemetry", json={"soil_vwc_pct": 25}, headers={"X-Device-Key": DEVICE_KEY})
        self.assertFalse(r.get_json()["command"]["irrigate"])
        self.assertEqual(r.get_json()["command"]["minutes"], 0)

    @patch("app.get_db")
    def test_out_of_range_reading(self, mock_db):
        cur = MagicMock()
        cur.fetchone.return_value = DEVICE_ROW
        mock_db.return_value = db_with(cur)
        r = self.client.post("/v2/telemetry", json={"soil_vwc_pct": 150}, headers={"X-Device-Key": DEVICE_KEY})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
