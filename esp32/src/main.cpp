// AgriSense field node - firmware v2
//
// What changed from v1 (see docs/ROADMAP.md, Phase 1):
//  * No hardcoded Wi-Fi or region/crop. A captive portal (WiFiManager) collects
//    Wi-Fi, server URL and the device key issued by POST /v2/devices. The farm
//    context (crop, soil, area, sowing date) lives on the server.
//  * Real units only: calibrated volumetric soil moisture (%), air temperature
//    and humidity, rain flag, battery voltage. The fake NDVI (from lux), the
//    lux->"sunlight hours" conversion and the uncalibrated analog pH are removed.
//  * The server returns a pump command (minutes). The node enforces its own
//    safety limits: max run time, minimum rest, and a moisture cutoff.
//  * If the server is unreachable for FALLBACK_AFTER_MS, a local hysteresis
//    controller keeps the crop alive (on below LOW, off above HIGH).
//  * Readings that cannot be sent are stored in flash (LittleFS), not RAM, so a
//    power cut does not lose them.
//
// Serial commands (115200 baud):
//   CAL DRY <vwc>   store current raw reading as the dry calibration point
//   CAL WET <vwc>   store current raw reading as the wet calibration point
//   PORTAL          reopen the setup portal
//   PUMP OFF        stop the pump immediately
//   STATUS          print state

#include <Arduino.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <esp_task_wdt.h>

#define FW_VERSION "2.0.0"

// ---------------- Pins ----------------
#define PIN_DHT 4
#define PIN_SOIL 34      // capacitive soil-moisture probe (analog)
#define PIN_BATTERY 35   // battery via 100k/100k divider
#define PIN_RAIN 32      // rain sensor digital output (LOW = wet)
#define PIN_RELAY 26     // pump relay / contactor driver (HIGH = on)
#define PIN_BUTTON 0     // BOOT button: hold 5 s at power-up to reopen portal

// ---------------- Timing and safety ----------------
static const uint32_t REPORT_INTERVAL_MS = 15UL * 60UL * 1000UL;   // report every 15 min
static const uint32_t FALLBACK_AFTER_MS = 6UL * 3600UL * 1000UL;   // local control after 6 h offline
static const uint32_t MAX_PUMP_MS = 180UL * 60UL * 1000UL;         // never run longer than 3 h
static const uint32_t MIN_REST_MS = 30UL * 60UL * 1000UL;          // rest 30 min between runs
static const uint32_t FALLBACK_RUN_MS = 20UL * 60UL * 1000UL;      // local mode: 20 min pulses
static const float FALLBACK_LOW_VWC = 20.0;   // local mode: start below this (%)
static const float FALLBACK_HIGH_VWC = 30.0;  // local mode: never run above this (%)
static const float CUTOFF_VWC = 45.0;         // any mode: stop if soil is this wet (%)
static const size_t MAX_BUFFER_BYTES = 64 * 1024;
static const char* BUFFER_PATH = "/buffer.jsonl";

DHT dht(PIN_DHT, DHT22);
Preferences prefs;

struct Config {
  String serverUrl;   // e.g. https://agrisense.example.com
  String deviceKey;
  int rawDry = 3000;  // capacitive probe: higher raw = drier
  float vwcDry = 10.0;
  int rawWet = 1300;
  float vwcWet = 45.0;
} cfg;

struct Reading {
  float soilVwc;
  float airT;
  float airRh;
  bool rain;
  float batteryV;
};

bool pumpOn = false;
uint32_t pumpStartedAt = 0, pumpRunFor = 0, pumpStoppedAt = 0;
uint32_t lastReportAt = 0, lastServerOkAt = 0;
bool everReported = false;

// ---------------- Config ----------------
void loadConfig() {
  prefs.begin("agrisense", true);
  cfg.serverUrl = prefs.getString("server", "");
  cfg.deviceKey = prefs.getString("key", "");
  cfg.rawDry = prefs.getInt("rawDry", cfg.rawDry);
  cfg.vwcDry = prefs.getFloat("vwcDry", cfg.vwcDry);
  cfg.rawWet = prefs.getInt("rawWet", cfg.rawWet);
  cfg.vwcWet = prefs.getFloat("vwcWet", cfg.vwcWet);
  prefs.end();
}

void saveConfig() {
  prefs.begin("agrisense", false);
  prefs.putString("server", cfg.serverUrl);
  prefs.putString("key", cfg.deviceKey);
  prefs.putInt("rawDry", cfg.rawDry);
  prefs.putFloat("vwcDry", cfg.vwcDry);
  prefs.putInt("rawWet", cfg.rawWet);
  prefs.putFloat("vwcWet", cfg.vwcWet);
  prefs.end();
}

void runPortal(bool force) {
  WiFiManager wm;
  WiFiManagerParameter pServer("server", "Server URL (https://...)", cfg.serverUrl.c_str(), 120);
  WiFiManagerParameter pKey("key", "Device key from /v2/devices", cfg.deviceKey.c_str(), 64);
  wm.addParameter(&pServer);
  wm.addParameter(&pKey);
  wm.setConfigPortalTimeout(300);
  String ap = "AgriSense-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok = force ? wm.startConfigPortal(ap.c_str()) : wm.autoConnect(ap.c_str());
  cfg.serverUrl = pServer.getValue();
  cfg.deviceKey = pKey.getValue();
  saveConfig();
  Serial.printf("Portal done, Wi-Fi %s\n", ok ? "connected" : "not connected");
}

// ---------------- Sensors ----------------
float rawToVwc(int raw) {
  if (cfg.rawDry == cfg.rawWet) return NAN;
  float v = cfg.vwcDry + (float)(raw - cfg.rawDry) * (cfg.vwcWet - cfg.vwcDry) / (float)(cfg.rawWet - cfg.rawDry);
  return constrain(v, 0.0f, 60.0f);
}

int readSoilRaw() {
  long sum = 0;
  for (int i = 0; i < 16; i++) {  // average out ADC noise
    sum += analogRead(PIN_SOIL);
    delay(5);
  }
  return (int)(sum / 16);
}

Reading readSensors() {
  Reading r;
  r.soilVwc = rawToVwc(readSoilRaw());
  r.airT = dht.readTemperature();
  r.airRh = dht.readHumidity();
  r.rain = digitalRead(PIN_RAIN) == LOW;
  r.batteryV = analogReadMilliVolts(PIN_BATTERY) * 2 / 1000.0f;
  return r;
}

// ---------------- Pump (all safety rules live here) ----------------
void pumpStop(const char* why) {
  if (pumpOn) Serial.printf("Pump OFF (%s)\n", why);
  digitalWrite(PIN_RELAY, LOW);
  if (pumpOn) pumpStoppedAt = millis();
  pumpOn = false;
}

bool pumpStart(uint32_t runMs, float soilVwc, const char* why) {
  if (pumpOn) return false;
  if (!isnan(soilVwc) && soilVwc >= CUTOFF_VWC) return false;
  if (pumpStoppedAt != 0 && millis() - pumpStoppedAt < MIN_REST_MS) return false;
  pumpRunFor = min(runMs, MAX_PUMP_MS);
  pumpStartedAt = millis();
  pumpOn = true;
  digitalWrite(PIN_RELAY, HIGH);
  Serial.printf("Pump ON for %lu s (%s)\n", (unsigned long)(pumpRunFor / 1000), why);
  return true;
}

void pumpTick(float soilVwc) {
  if (!pumpOn) return;
  if (millis() - pumpStartedAt >= pumpRunFor) pumpStop("run time reached");
  else if (!isnan(soilVwc) && soilVwc >= CUTOFF_VWC) pumpStop("soil saturated");
}

// ---------------- Flash buffer ----------------
void bufferAppend(const String& line) {
  File f = LittleFS.open(BUFFER_PATH, FILE_APPEND);
  if (!f) return;
  if (f.size() + line.length() < MAX_BUFFER_BYTES) f.println(line);
  f.close();
}

// ---------------- Networking ----------------
int postJson(const String& body, JsonDocument& response) {
  if (WiFi.status() != WL_CONNECTED || cfg.serverUrl.isEmpty() || cfg.deviceKey.isEmpty()) return -1;
  HTTPClient http;
  WiFiClientSecure secure;
  WiFiClient plain;
  String url = cfg.serverUrl + "/v2/telemetry";
  if (url.startsWith("https://")) {
    // TODO(pilot): pin the server's CA with secure.setCACert(...) before field deployment.
    secure.setInsecure();
    http.begin(secure, url);
  } else {
    http.begin(plain, url);
  }
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", cfg.deviceKey);
  int code = http.POST(body);
  if (code == 200) deserializeJson(response, http.getString());
  http.end();
  return code;
}

String buildPayload(const Reading& r) {
  JsonDocument doc;
  if (!isnan(r.soilVwc)) doc["soil_vwc_pct"] = serialized(String(r.soilVwc, 1));
  if (!isnan(r.airT)) doc["air_temp_c"] = serialized(String(r.airT, 1));
  if (!isnan(r.airRh)) doc["air_rh_pct"] = serialized(String(r.airRh, 1));
  doc["rain_mm"] = r.rain ? 1.0 : 0.0;  // tipping-bucket gauge recommended for real mm
  doc["battery_v"] = serialized(String(r.batteryV, 2));
  doc["firmware"] = FW_VERSION;
  String out;
  serializeJson(doc, out);
  return out;
}

void flushBuffer() {
  if (!LittleFS.exists(BUFFER_PATH)) return;
  File f = LittleFS.open(BUFFER_PATH, FILE_READ);
  String remaining;
  int sent = 0;
  while (f.available()) {
    String line = f.readStringUntil('\n');
    line.trim();
    if (line.isEmpty()) continue;
    JsonDocument ignored;
    if (remaining.isEmpty() && postJson(line, ignored) == 200) sent++;
    else remaining += line + "\n";
    esp_task_wdt_reset();
  }
  f.close();
  File w = LittleFS.open(BUFFER_PATH, FILE_WRITE);
  w.print(remaining);
  w.close();
  if (sent) Serial.printf("Flushed %d buffered readings\n", sent);
}

void report(const Reading& r) {
  String payload = buildPayload(r);
  JsonDocument resp;
  int code = postJson(payload, resp);
  if (code == 200) {
    lastServerOkAt = millis();
    everReported = true;
    flushBuffer();
    bool irrigate = resp["command"]["irrigate"] | false;
    int minutes = resp["command"]["minutes"] | 0;
    Serial.printf("Server: irrigate=%d minutes=%d\n", irrigate, minutes);
    if (irrigate && minutes > 0) pumpStart((uint32_t)minutes * 60000UL, r.soilVwc, "server command");
    return;
  }
  Serial.printf("Report failed (HTTP %d), buffering\n", code);
  bufferAppend(payload);

  bool offlineTooLong = everReported ? (millis() - lastServerOkAt > FALLBACK_AFTER_MS) : (millis() > FALLBACK_AFTER_MS);
  if (offlineTooLong && !isnan(r.soilVwc)) {
    if (r.soilVwc < FALLBACK_LOW_VWC && !r.rain) pumpStart(FALLBACK_RUN_MS, r.soilVwc, "local fallback");
    else if (r.soilVwc > FALLBACK_HIGH_VWC) pumpStop("local fallback: moist enough");
  }
}

// ---------------- Serial commands ----------------
void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.startsWith("CAL DRY ") || cmd.startsWith("CAL WET ")) {
    int raw = readSoilRaw();
    float vwc = cmd.substring(8).toFloat();
    if (cmd.startsWith("CAL DRY")) { cfg.rawDry = raw; cfg.vwcDry = vwc; }
    else { cfg.rawWet = raw; cfg.vwcWet = vwc; }
    saveConfig();
    Serial.printf("Calibration saved: raw %d = %.1f%% VWC\n", raw, vwc);
  } else if (cmd == "PORTAL") {
    pumpStop("setup portal");
    runPortal(true);
  } else if (cmd == "PUMP OFF") {
    pumpStop("manual");
  } else if (cmd == "STATUS") {
    Reading r = readSensors();
    Serial.printf("fw %s | soil %.1f%% | air %.1fC %.0f%% | rain %d | batt %.2fV | pump %d | wifi %d\n",
                  FW_VERSION, r.soilVwc, r.airT, r.airRh, r.rain, r.batteryV, pumpOn, WiFi.status() == WL_CONNECTED);
  }
}

// ---------------- Setup / loop ----------------
void setup() {
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, LOW);  // pump off before anything else
  Serial.begin(115200);
  Serial.printf("\nAgriSense node fw %s\n", FW_VERSION);

  pinMode(PIN_RAIN, INPUT_PULLUP);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  analogReadResolution(12);
  dht.begin();
  if (!LittleFS.begin(true)) Serial.println("LittleFS mount failed");
  loadConfig();

#if ESP_IDF_VERSION_MAJOR >= 5
  esp_task_wdt_config_t wdt = {.timeout_ms = 60000, .idle_core_mask = 0, .trigger_panic = true};
  esp_task_wdt_reconfigure(&wdt);
#else
  esp_task_wdt_init(60, true);  // Arduino core 2.x (ESP-IDF 4.4)
#endif
  esp_task_wdt_add(NULL);

  bool holdButton = digitalRead(PIN_BUTTON) == LOW;
  uint32_t t0 = millis();
  while (holdButton && digitalRead(PIN_BUTTON) == LOW && millis() - t0 < 5000) delay(10);
  bool forcePortal = holdButton && millis() - t0 >= 5000;
  runPortal(forcePortal || cfg.serverUrl.isEmpty() || cfg.deviceKey.isEmpty());
  lastReportAt = millis() - REPORT_INTERVAL_MS;  // report right away
}

void loop() {
  esp_task_wdt_reset();
  handleSerial();

  static uint32_t lastTick = 0;
  if (millis() - lastTick >= 5000) {
    lastTick = millis();
    pumpTick(pumpOn ? rawToVwc(readSoilRaw()) : NAN);
  }

  if (millis() - lastReportAt >= REPORT_INTERVAL_MS) {
    lastReportAt = millis();
    if (WiFi.status() != WL_CONNECTED) WiFi.reconnect();
    Reading r = readSensors();
    Serial.printf("soil %.1f%% air %.1fC %.0f%% rain %d batt %.2fV\n", r.soilVwc, r.airT, r.airRh, r.rain, r.batteryV);
    report(r);
  }
  delay(50);
}
