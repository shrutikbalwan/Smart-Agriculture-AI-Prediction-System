# AgriSense: Real-World Deployment Roadmap

Goal: a system a farmer near Solapur can rely on for a full season. It should give correct irrigation volumes, early disease alerts and advice in Marathi on WhatsApp. The headline pilot metric is **litres of water saved per acre per season**, with yield equal or better.

## Audit (September 2026)

| Area | Finding | Status |
| --- | --- | --- |
| Data | Training dataset is synthetic; region labels share the same coordinates | Documented; Phase 2 |
| Models | Heat stress, soil health, irrigation time copy a single threshold; rain impact is one class | Replaced by `backend/agronomy.py` |
| Models | Disease prediction is close to chance; yield driven by longitude | Documented; Phase 2 |
| Firmware | Sent region/crop "Auto", always rejected (HTTP 400) | Fixed: device registry |
| Firmware | lux→"sunlight hours", NDVI from lux, uncalibrated pH | Removed |
| Firmware | Pump without hysteresis or max run time; RAM-only buffer | Fixed |
| Backend | `json` not imported, so audit log never written | Fixed |
| Backend | Unauthenticated delete/export; default secrets; open CORS | Fixed |
| Backend | `from db import` broke `gunicorn backend.app:app` | Fixed |
| Repo | Tests not run in CI | Fixed: `.github/workflows/ci.yml` |

## Phase 1: make it honest and working (this PR)

- FAO-56 irrigation engine with reasons (`/v2/advise`)
- Device registry and per-device keys (`/v2/devices`, `/v2/telemetry`)
- Firmware v2: captive portal, calibrated soil moisture, pump safety, flash buffer, offline fallback
- Security fixes, CI for tests and firmware build, honest README

**Exit gate:** a bench ESP32 posts readings and receives an irrigation volume end to end, and CI is green.

## Phase 2: real agronomy and data (months 1–3)

| Capability | Replace with | Data source |
| --- | --- | --- |
| Crop vigour | Sentinel-2 NDVI per plot polygon | Copernicus via Google Earth Engine |
| Disease detection | Leaf-photo CNN (MobileNetV3 / EfficientNet-Lite) | PlantVillage + pilot photos |
| Disease risk | Weather-driven models for local diseases | Published thresholds + weather |
| Fertilizer | Soil-test-based NPK dose (STCR) | Soil Health Card / lab test |
| Yield | Gradient boosting on district history + weather + NDVI | data.gov.in, IMD |
| Crop choice | Suitability + mandi price + water budget | Agmarknet |

## Phase 3: field-grade hardware (months 2–4)

Capacitive probes at two depths, RS485 NPK/pH/EC probe, LoRa (SX1262) to a farm gateway, MQTT over TLS, solar + 18650 + deep sleep, IP65 enclosure, flow meter and dry-run protection, signed OTA, TFLite Micro on ESP32-S3 for offline decisions.

## Phase 4: product and startup (months 3–12)

WhatsApp-first advice in Marathi, a 10-farm pilot with control plots for one season, and FPO / B2B / government-scheme business models. Track litres saved, yield, advice-followed rate, weekly active farmers, node uptime and cost per node.
