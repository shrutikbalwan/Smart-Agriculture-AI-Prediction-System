"""Summarise an OpenWeatherMap 5-day/3-hour forecast into agronomy inputs."""

from __future__ import annotations

import math
from typing import Optional

import requests

OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def wind_10m_to_2m(u10: float) -> float:
    """FAO-56 eq. 47: convert wind speed measured at 10 m to 2 m."""
    return u10 * 4.87 / math.log(67.8 * 10 - 5.42)


def summarise_forecast(payload: dict) -> dict:
    """Turn an OWM forecast payload into daily inputs for the agronomy engine.

    Uses the next 8 slots (24 h) for temperature, humidity and wind, and the
    next 16 slots (48 h) for rainfall.
    """
    slots = payload.get("list") or []
    if not slots:
        raise ValueError("forecast has no data")
    day, two_days = slots[:8], slots[:16]
    temps_max = [s["main"].get("temp_max", s["main"]["temp"]) for s in day]
    temps_min = [s["main"].get("temp_min", s["main"]["temp"]) for s in day]
    rh = [s["main"]["humidity"] for s in day if "humidity" in s["main"]]
    wind = [s.get("wind", {}).get("speed") for s in day if s.get("wind", {}).get("speed") is not None]
    rain_24h = sum((s.get("rain") or {}).get("3h", 0.0) for s in day)
    rain_48h = sum((s.get("rain") or {}).get("3h", 0.0) for s in two_days)
    return {
        "t_max": round(max(temps_max), 1),
        "t_min": round(min(temps_min), 1),
        "rh_max": max(rh) if rh else None,
        "rh_min": min(rh) if rh else None,
        "wind_u2": round(wind_10m_to_2m(sum(wind) / len(wind)), 2) if wind else None,
        "rain_next_24h_mm": round(rain_24h, 1),
        "rain_forecast_48h_mm": round(rain_48h, 1),
        "source": "openweathermap-forecast",
    }


def fetch_forecast_summary(lat: float, lon: float, api_key: str, timeout: int = 10) -> Optional[dict]:
    """Fetch and summarise the forecast; returns None when unavailable."""
    if not api_key or lat is None or lon is None:
        return None
    try:
        resp = requests.get(
            OWM_FORECAST_URL,
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        return summarise_forecast(resp.json())
    except (requests.RequestException, ValueError, KeyError):
        return None
