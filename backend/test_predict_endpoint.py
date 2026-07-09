import unittest

from app import app


class PredictEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_predict_returns_success_for_valid_payload(self):
        payload = {
            "region": "North India",
            "crop_type": "Rice",
            "soil_moisture_%": 35,
            "soil_pH": 6.5,
            "temperature_C": 28,
            "rainfall_mm": 120,
            "humidity_%": 70,
            "sunlight_hours": 8,
            "irrigation_type": "Drip",
            "fertilizer_type": "Organic",
            "pesticide_usage_ml": 10,
            "total_days": 90,
            "latitude": 20.5,
            "longitude": 78.9,
            "NDVI_index": 0.7,
        }

        response = self.client.post("/predict", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertIn("prediction", body)


if __name__ == "__main__":
    unittest.main()
