"""Tests for the FAO-56 agronomy engine, checked against FAO-56 worked examples."""

import math
import unittest
from datetime import date

import agronomy as ag
from weather_service import summarise_forecast, wind_10m_to_2m


class TestFao56(unittest.TestCase):
    def test_et0_matches_fao56_example_18(self):
        # FAO-56 Example 18: Brussels, 6 July -> ET0 = 3.9 mm/day
        r = ag.et0_penman_monteith(
            t_max=21.5, t_min=12.3, lat_deg=50.8, day_of_year=187, elevation_m=100,
            rh_max=84, rh_min=63, wind_u2=2.078, sunshine_hours=9.25,
        )
        self.assertAlmostEqual(r["et0_mm"], 3.9, delta=0.1)
        self.assertEqual(r["radiation_method"], "sunshine")

    def test_extraterrestrial_radiation_example_8(self):
        # FAO-56 Example 8: 20 deg S, 3 September -> Ra = 32.2 MJ/m2/day
        ra, _ = ag.extraterrestrial_radiation(-20.0, 246)
        self.assertAlmostEqual(ra, 32.2, delta=0.2)

    def test_sat_vapour_pressure(self):
        # FAO-56 Annex 2, Table 2.3: e0(25 C) = 3.168 kPa
        self.assertAlmostEqual(ag.sat_vapour_pressure(25.0), 3.168, places=2)

    def test_wind_conversion_example_14(self):
        # FAO-56 Example 14: 3.2 m/s at 10 m -> 2.4 m/s at 2 m
        self.assertAlmostEqual(wind_10m_to_2m(3.2), 2.4, delta=0.05)

    def test_hargreaves_fallback_is_reasonable_for_solapur_summer(self):
        r = ag.et0_penman_monteith(t_max=40, t_min=25, lat_deg=17.66, day_of_year=120, elevation_m=457)
        self.assertEqual(r["radiation_method"], "hargreaves")
        self.assertTrue(5 < r["et0_mm"] < 10)

    def test_invalid_temperatures(self):
        with self.assertRaises(ag.AgronomyError):
            ag.et0_penman_monteith(t_max=10, t_min=20, lat_deg=17, day_of_year=100)


class TestCropCurve(unittest.TestCase):
    def test_stages_and_kc(self):
        onion = ag.get_crop("onion")
        self.assertEqual(ag.crop_stage(onion, 5), ("initial", 0.70))
        stage, kc = ag.crop_stage(onion, 15 + 25 + 10)
        self.assertEqual((stage, kc), ("mid-season", 1.05))
        stage, kc = ag.crop_stage(onion, 15 + 12)
        self.assertEqual(stage, "development")
        self.assertTrue(0.70 < kc < 1.05)

    def test_aliases_and_unknown(self):
        self.assertEqual(ag.get_crop("Jowar").name, "Sorghum (jowar)")
        with self.assertRaises(ag.AgronomyError):
            ag.get_crop("banana")
        with self.assertRaises(ag.AgronomyError):
            ag.get_soil("peat")

    def test_effective_rain(self):
        self.assertEqual(ag.effective_rain(3), 0.0)
        self.assertEqual(ag.effective_rain(20), 15.0)


class TestIrrigationAdvice(unittest.TestCase):
    base = dict(
        crop="onion", sowing_date=date(2026, 1, 1), today=date(2026, 2, 20),
        soil_texture="clay", area_m2=1000, irrigation_method="drip",
        weather={"t_max": 34, "t_min": 18, "rh_mean": 45, "wind_u2": 2},
        latitude=17.66, elevation_m=457, pump_flow_lph=1000,
    )

    def test_moist_soil_no_irrigation(self):
        a = ag.irrigation_advice(**self.base, soil_vwc_pct=34)
        self.assertFalse(a.irrigate)
        self.assertEqual(a.litres, 0)
        self.assertIn("below", a.reasons[-1])

    def test_dry_soil_irrigates_and_computes_volume(self):
        a = ag.irrigation_advice(**self.base, soil_vwc_pct=25)
        self.assertTrue(a.irrigate)
        # clay FC 0.36, root depth 0.4 m -> depletion = 1000*(0.36-0.25)*0.4 = 44 mm
        self.assertAlmostEqual(a.net_mm, 44.0, delta=0.1)
        self.assertAlmostEqual(a.gross_mm, round(44.0 / 0.9, 1), delta=0.1)
        self.assertEqual(a.litres, round(a.gross_mm * 1000 * 0.4))
        self.assertEqual(a.minutes, min(180, math.ceil(a.litres / 1000 * 60)))
        self.assertIn("etc_mm", a.details)

    def test_forecast_rain_defers_irrigation(self):
        a = ag.irrigation_advice(**self.base, soil_vwc_pct=25, rain_forecast_48h_mm=80)
        self.assertFalse(a.irrigate)
        self.assertIn("forecast", a.reasons[-1])

    def test_pump_time_is_capped(self):
        a = ag.irrigation_advice(**{**self.base, "area_m2": 50000}, soil_vwc_pct=23)
        self.assertEqual(a.minutes, 180)
        self.assertTrue(any("capped" in r for r in a.reasons))

    def test_no_sensor_uses_etc(self):
        a = ag.irrigation_advice(**self.base)
        self.assertTrue(a.irrigate)
        self.assertAlmostEqual(a.net_mm, a.details["etc_mm"], delta=0.1)

    def test_needs_sensor_or_weather(self):
        with self.assertRaises(ag.AgronomyError):
            ag.irrigation_advice(**{**self.base, "weather": None})

    def test_future_sowing_rejected(self):
        with self.assertRaises(ag.AgronomyError):
            ag.irrigation_advice(**{**self.base, "sowing_date": date(2027, 1, 1)}, soil_vwc_pct=30)

    def test_heat_stress_and_window(self):
        a = ag.irrigation_advice(**{**self.base, "weather": {"t_max": 41, "t_min": 26}}, soil_vwc_pct=30)
        self.assertEqual(a.details["heat_stress"], "high")
        self.assertIn("Early morning", a.details["best_irrigation_window"])


class TestForecastSummary(unittest.TestCase):
    def test_summary(self):
        slots = [
            {"main": {"temp": 30, "temp_max": 30 + i % 3, "temp_min": 20 + i % 2, "humidity": 50 + i},
             "wind": {"speed": 3.2}, "rain": {"3h": 1.0} if i < 4 else {}}
            for i in range(16)
        ]
        s = summarise_forecast({"list": slots})
        self.assertEqual(s["t_max"], 32)
        self.assertEqual(s["t_min"], 20)
        self.assertEqual(s["rain_forecast_48h_mm"], 4.0)
        self.assertAlmostEqual(s["wind_u2"], 2.4, delta=0.05)

    def test_empty(self):
        with self.assertRaises(ValueError):
            summarise_forecast({"list": []})


if __name__ == "__main__":
    unittest.main()
