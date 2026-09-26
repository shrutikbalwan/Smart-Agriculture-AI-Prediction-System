"""Transparent agronomy engine for AgriSense.

Replaces the ML models that were only re-learning single thresholds from a
synthetic dataset (heat stress, soil health, irrigation time, rain impact)
with documented, explainable agronomy:

* FAO-56 Penman-Monteith reference evapotranspiration (ET0)
  Allen et al. (1998), FAO Irrigation and Drainage Paper 56.
  https://www.fao.org/4/x0490e/x0490e00.htm
* Single crop-coefficient curve (Kc) by growth stage (FAO-56 ch. 6).
* Root-zone soil-water balance: irrigate when depletion exceeds the readily
  available water (RAW = p * TAW), refill to field capacity.

Crop and soil parameters are FAO-56 typical values (Tables 11, 12, 19, 22).
They are starting points and MUST be calibrated for local varieties and soils.
Every function is pure (no I/O) so it can be unit-tested and reused on-device.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CropParams:
    name: str
    stage_days: tuple  # (initial, development, mid-season, late-season)
    kc_ini: float
    kc_mid: float
    kc_end: float
    root_depth_m: float  # effective root depth at full development
    depletion_p: float  # fraction of TAW that can be used before stress
    heat_stress_c: float  # daily Tmax above which the crop is stressed
    note: str = "FAO-56 Tables 11/12/22 typical values"


CROPS = {
    "sugarcane": CropParams("Sugarcane", (35, 60, 190, 120), 0.40, 1.25, 0.75, 1.2, 0.65, 38),
    "sorghum": CropParams("Sorghum (jowar)", (20, 35, 40, 30), 0.30, 1.05, 0.55, 1.0, 0.55, 40),
    "onion": CropParams("Onion (dry)", (15, 25, 70, 40), 0.70, 1.05, 0.75, 0.4, 0.30, 35),
    "grapes": CropParams("Grapes (table)", (20, 40, 120, 60), 0.30, 0.85, 0.45, 1.0, 0.35, 38),
    "pomegranate": CropParams(
        "Pomegranate", (60, 90, 120, 95), 0.40, 0.80, 0.60, 1.0, 0.50, 40,
        note="Not in FAO-56; approximate orchard values, calibrate locally",
    ),
    "cotton": CropParams("Cotton", (30, 50, 60, 55), 0.35, 1.18, 0.60, 1.0, 0.65, 40),
    "maize": CropParams("Maize (grain)", (25, 40, 40, 30), 0.30, 1.20, 0.35, 1.0, 0.55, 35),
    "wheat": CropParams("Wheat", (20, 25, 60, 30), 0.30, 1.15, 0.30, 1.0, 0.55, 32),
    "rice": CropParams("Rice", (30, 30, 60, 30), 1.05, 1.20, 0.75, 0.5, 0.20, 35),
    "soybean": CropParams("Soybean", (15, 15, 40, 15), 0.40, 1.15, 0.50, 0.6, 0.50, 35),
}


@dataclass(frozen=True)
class SoilParams:
    name: str
    field_capacity: float  # volumetric fraction (m3/m3)
    wilting_point: float


# FAO-56 Table 19 mid-range values. Solapur black cotton soil ~ "clay".
SOILS = {
    "sand": SoilParams("Sand", 0.12, 0.04),
    "sandy_loam": SoilParams("Sandy loam", 0.18, 0.08),
    "loam": SoilParams("Loam", 0.25, 0.12),
    "clay_loam": SoilParams("Clay loam", 0.32, 0.17),
    "clay": SoilParams("Clay / black cotton soil", 0.36, 0.22),
}

# Application efficiency (fraction of applied water that reaches the root zone)
IRRIGATION_EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "furrow": 0.60, "flood": 0.50, "manual": 0.60}

# Fraction of the field surface actually wetted (FAO-56 Table 20). Drip only
# wets the soil around emitters, so volumes are scaled down accordingly.
WETTED_FRACTION = {"drip": 0.40, "sprinkler": 1.0, "furrow": 0.80, "flood": 1.0, "manual": 1.0}

SIGMA = 4.903e-9  # Stefan-Boltzmann, MJ K-4 m-2 day-1


class AgronomyError(ValueError):
    """Raised for invalid agronomy inputs (mapped to HTTP 400)."""


# --------------------------------------------------------------------------
# FAO-56 reference evapotranspiration
# --------------------------------------------------------------------------


def sat_vapour_pressure(t_c: float) -> float:
    """e°(T) in kPa, FAO-56 eq. 11."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def extraterrestrial_radiation(lat_deg: float, day_of_year: int) -> tuple:
    """Ra (MJ m-2 day-1) and daylight hours N, FAO-56 eqs. 21-25, 34."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    decl = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    return ra, 24 / math.pi * ws


def et0_penman_monteith(
    *,
    t_max: float,
    t_min: float,
    lat_deg: float,
    day_of_year: int,
    elevation_m: float = 0.0,
    rh_mean: Optional[float] = None,
    rh_max: Optional[float] = None,
    rh_min: Optional[float] = None,
    wind_u2: float = 2.0,
    solar_rad: Optional[float] = None,
    sunshine_hours: Optional[float] = None,
) -> dict:
    """Daily FAO-56 Penman-Monteith ET0 in mm/day.

    Radiation: measured ``solar_rad`` (MJ m-2 day-1) if given, else Angstrom
    from ``sunshine_hours``, else Hargreaves temperature-difference estimate.
    Humidity: RHmax/RHmin (eq. 17) if both given, else RHmean (eq. 19).
    Wind: ``wind_u2`` at 2 m (m/s); FAO-56 recommends 2 m/s when unknown.
    """
    if t_max < t_min:
        raise AgronomyError("t_max must be >= t_min")
    if not (-90 <= lat_deg <= 90):
        raise AgronomyError("latitude out of range")
    if not (1 <= day_of_year <= 366):
        raise AgronomyError("day_of_year out of range")

    t_mean = (t_max + t_min) / 2
    pressure = 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    e_tmax, e_tmin = sat_vapour_pressure(t_max), sat_vapour_pressure(t_min)
    es = (e_tmax + e_tmin) / 2

    if rh_max is not None and rh_min is not None:
        ea = (e_tmin * rh_max / 100 + e_tmax * rh_min / 100) / 2
    elif rh_mean is not None:
        ea = rh_mean / 100 * es
    else:
        ea = sat_vapour_pressure(t_min)  # FAO-56 eq. 48: Tdew ~ Tmin when humidity missing

    delta = 4098 * sat_vapour_pressure(t_mean) / (t_mean + 237.3) ** 2
    ra, daylight = extraterrestrial_radiation(lat_deg, day_of_year)

    if solar_rad is not None:
        rs, rad_method = solar_rad, "measured"
    elif sunshine_hours is not None:
        rs, rad_method = (0.25 + 0.50 * min(sunshine_hours, daylight) / daylight) * ra, "sunshine"
    else:
        rs, rad_method = 0.16 * math.sqrt(t_max - t_min) * ra, "hargreaves"

    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = 0.77 * rs
    rs_rso = min(rs / rso, 1.0) if rso > 0 else 0.5
    rnl = SIGMA * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2 * (
        0.34 - 0.14 * math.sqrt(max(ea, 0))
    ) * (1.35 * rs_rso - 0.35)
    rn = rns - rnl

    et0 = (0.408 * delta * rn + gamma * 900 / (t_mean + 273) * wind_u2 * (es - ea)) / (
        delta + gamma * (1 + 0.34 * wind_u2)
    )
    return {"et0_mm": round(max(et0, 0.0), 2), "radiation_method": rad_method}


# --------------------------------------------------------------------------
# Crop coefficient and water balance
# --------------------------------------------------------------------------


def get_crop(crop: str) -> CropParams:
    key = (crop or "").strip().lower().replace(" ", "_")
    aliases = {"jowar": "sorghum", "grape": "grapes", "cane": "sugarcane", "soya": "soybean"}
    key = aliases.get(key, key)
    if key not in CROPS:
        raise AgronomyError(f"Unknown crop '{crop}'. Supported: {sorted(CROPS)}")
    return CROPS[key]


def get_soil(texture: str) -> SoilParams:
    key = (texture or "").strip().lower().replace(" ", "_")
    if key not in SOILS:
        raise AgronomyError(f"Unknown soil texture '{texture}'. Supported: {sorted(SOILS)}")
    return SOILS[key]


def crop_stage(crop: CropParams, days_after_sowing: int) -> tuple:
    """Return (stage name, Kc) for a day, FAO-56 single Kc curve (fig. 25)."""
    ini, dev, mid, late = crop.stage_days
    d = max(0, days_after_sowing)
    if d <= ini:
        return "initial", crop.kc_ini
    if d <= ini + dev:
        f = (d - ini) / dev
        return "development", crop.kc_ini + f * (crop.kc_mid - crop.kc_ini)
    if d <= ini + dev + mid:
        return "mid-season", crop.kc_mid
    if d <= ini + dev + mid + late:
        f = (d - ini - dev - mid) / late
        return "late-season", crop.kc_mid + f * (crop.kc_end - crop.kc_mid)
    return "after harvest window", crop.kc_end


def effective_rain(rain_mm: float) -> float:
    """Simple daily effective rainfall: small showers (<5 mm) mostly evaporate."""
    rain_mm = max(0.0, rain_mm or 0.0)
    return 0.0 if rain_mm < 5 else round(0.75 * rain_mm, 2)


def heat_stress_level(crop: CropParams, t_max: Optional[float]) -> str:
    if t_max is None:
        return "unknown"
    if t_max >= crop.heat_stress_c + 4:
        return "high"
    if t_max >= crop.heat_stress_c:
        return "moderate"
    return "low"


def best_irrigation_window(method: str, t_max: Optional[float], wind_u2: Optional[float]) -> str:
    if method == "sprinkler" and wind_u2 is not None and wind_u2 > 4:
        return "Evening (after 6 pm), when wind drops"
    if t_max is not None and t_max >= 35:
        return "Early morning (5-8 am), to cut evaporation losses"
    return "Early morning (5-8 am)"


@dataclass
class Advice:
    irrigate: bool
    net_mm: float
    gross_mm: float
    litres: float
    minutes: Optional[int]
    reasons: list = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "irrigate": self.irrigate,
            "net_irrigation_mm": self.net_mm,
            "gross_irrigation_mm": self.gross_mm,
            "litres": self.litres,
            "pump_minutes": self.minutes,
            "reasons": self.reasons,
            "details": self.details,
        }


def irrigation_advice(
    *,
    crop: str,
    sowing_date: date,
    today: date,
    soil_texture: str,
    area_m2: float,
    irrigation_method: str = "drip",
    soil_vwc_pct: Optional[float] = None,
    rain_today_mm: float = 0.0,
    rain_forecast_48h_mm: float = 0.0,
    weather: Optional[dict] = None,
    latitude: Optional[float] = None,
    elevation_m: float = 0.0,
    pump_flow_lph: Optional[float] = None,
    max_pump_minutes: int = 180,
    wetted_fraction: Optional[float] = None,
) -> Advice:
    """Decide whether and how much to irrigate, with human-readable reasons.

    With a soil-moisture reading, uses root-zone depletion (FAO-56 ch. 8):
    irrigate when depletion >= RAW, refill to field capacity.
    Without one, replaces today's crop water use (ETc) minus effective rain.
    """
    c = get_crop(crop)
    s = get_soil(soil_texture)
    method = (irrigation_method or "drip").strip().lower()
    if method not in IRRIGATION_EFFICIENCY:
        raise AgronomyError(f"Unknown irrigation method '{irrigation_method}'. Supported: {sorted(IRRIGATION_EFFICIENCY)}")
    if area_m2 is None or area_m2 <= 0:
        raise AgronomyError("area_m2 must be > 0")
    if today < sowing_date:
        raise AgronomyError("sowing_date is in the future")

    das = (today - sowing_date).days
    stage, kc = crop_stage(c, das)
    efficiency = IRRIGATION_EFFICIENCY[method]
    fw = wetted_fraction if wetted_fraction is not None else WETTED_FRACTION[method]
    if not (0 < fw <= 1):
        raise AgronomyError("wetted_fraction must be in (0, 1]")
    reasons, details = [], {
        "crop": c.name, "crop_params_source": c.note, "soil": s.name,
        "days_after_sowing": das, "growth_stage": stage, "kc": round(kc, 2),
        "irrigation_efficiency": efficiency, "wetted_fraction": fw,
    }

    # Crop water use today (needs weather)
    etc = None
    w = weather or {}
    if w.get("t_max") is not None and w.get("t_min") is not None and latitude is not None:
        et = et0_penman_monteith(
            t_max=w["t_max"], t_min=w["t_min"], lat_deg=latitude,
            day_of_year=today.timetuple().tm_yday, elevation_m=elevation_m,
            rh_mean=w.get("rh_mean"), rh_max=w.get("rh_max"), rh_min=w.get("rh_min"),
            wind_u2=w.get("wind_u2", 2.0) if w.get("wind_u2") is not None else 2.0,
            solar_rad=w.get("solar_rad"), sunshine_hours=w.get("sunshine_hours"),
        )
        etc = round(et["et0_mm"] * kc, 2)
        details.update({"et0_mm": et["et0_mm"], "etc_mm": etc, "radiation_method": et["radiation_method"]})
        reasons.append(f"Crop water use today is about {etc} mm ({c.name}, {stage} stage, Kc {kc:.2f}).")

    peff_today = effective_rain(rain_today_mm)
    peff_forecast = effective_rain(rain_forecast_48h_mm)
    details.update({"effective_rain_today_mm": peff_today, "effective_rain_forecast_48h_mm": peff_forecast})

    zr = c.root_depth_m if stage not in ("initial",) else max(0.15, c.root_depth_m * 0.4)
    taw = 1000 * (s.field_capacity - s.wilting_point) * zr
    raw = c.depletion_p * taw
    details.update({"root_depth_m": round(zr, 2), "taw_mm": round(taw, 1), "raw_mm": round(raw, 1)})

    if soil_vwc_pct is not None:
        theta = max(0.0, min(soil_vwc_pct / 100, 0.6))
        depletion = max(0.0, 1000 * (s.field_capacity - theta) * zr - peff_today)
        details.update({"soil_vwc_pct": soil_vwc_pct, "root_zone_depletion_mm": round(depletion, 1)})
        if theta <= s.wilting_point:
            reasons.append("Soil moisture is at or below wilting point: irrigate now.")
        if depletion < raw:
            reasons.append(
                f"Root-zone depletion {depletion:.1f} mm is below the {raw:.1f} mm the crop can use without stress."
            )
            net = 0.0
        elif peff_forecast >= depletion:
            reasons.append(
                f"Depletion is {depletion:.1f} mm, but about {peff_forecast:.1f} mm of useful rain is forecast in 48 h: wait."
            )
            net = 0.0
        else:
            net = depletion - peff_forecast
            reasons.append(
                f"Depletion {depletion:.1f} mm exceeds the {raw:.1f} mm stress threshold: refill the root zone."
            )
            if peff_forecast > 0:
                reasons.append(f"Reduced by {peff_forecast:.1f} mm of forecast rain.")
    elif etc is not None:
        net = max(0.0, etc - peff_today)
        reasons.append("No soil sensor reading: replacing today's crop water use minus effective rain.")
        if peff_forecast >= net and net > 0:
            reasons.append(f"About {peff_forecast:.1f} mm of useful rain is forecast in 48 h: wait.")
            net = 0.0
    else:
        raise AgronomyError("Need either soil_vwc_pct or weather (t_max, t_min) with latitude")

    net = round(net, 1)
    gross = round(net / efficiency, 1)
    litres = round(gross * area_m2 * fw, 0)  # 1 mm over 1 m2 = 1 litre
    minutes = None
    if pump_flow_lph and pump_flow_lph > 0 and litres > 0:
        minutes = int(math.ceil(litres / pump_flow_lph * 60))
        if minutes > max_pump_minutes:
            reasons.append(f"Pump time capped at {max_pump_minutes} min for safety; split into more sessions.")
            minutes = max_pump_minutes

    details.update({
        "heat_stress": heat_stress_level(c, w.get("t_max")),
        "best_irrigation_window": best_irrigation_window(method, w.get("t_max"), w.get("wind_u2")),
    })
    return Advice(net > 0, net, gross, litres, minutes, reasons, details)
