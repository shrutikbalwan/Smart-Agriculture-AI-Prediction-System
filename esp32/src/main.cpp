#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <BH1750.h>
#include <Adafruit_SSD1306.h>
#include <TinyGPSPlus.h>
#include <Wire.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.100:5000/predict";
const int HTTP_TIMEOUT = 30000;
const int SENSOR_INTERVAL_MS = 60000;
const int MAX_RETRIES = 3;
const int RETRY_DELAY_MS = 5000;
const int MAX_OFFLINE_RECORDS = 100;

#define DHTPIN 4
#define DHTTYPE DHT22
#define SOIL_MOISTURE_PIN 34
#define PH_SENSOR_PIN 35
#define RAIN_SENSOR_PIN 32
#define RELAY_PIN 26
#define OLED_SDA 21
#define OLED_SCL 22

DHT dht(DHTPIN, DHTTYPE);
BH1750 lightMeter;
TinyGPSPlus gps;
Adafruit_SSD1306 display(128, 64, &Wire, -1);
HTTPClient http;

struct SensorData {
  float temperature;
  float humidity;
  int soilMoisture;
  float soilPH;
  bool rainDetected;
  float sunlight;
  float latitude;
  float longitude;
  float ndvi;
  unsigned long timestamp;
};

SensorData offlineBuffer[MAX_OFFLINE_RECORDS];
int offlineCount = 0;
unsigned long lastSensorRead = 0;
bool useDummyMode = false;

SensorData readDummySensors() {
  SensorData data;
  data.temperature = random(200, 400) / 10.0;
  data.humidity = random(400, 900) / 10.0;
  data.soilMoisture = random(20, 80);
  data.soilPH = random(55, 80) / 10.0;
  data.rainDetected = random(0, 2);
  data.sunlight = random(0, 100000) / 1000.0;
  data.latitude = 28.61 + (random(-100, 100) / 10000.0);
  data.longitude = 77.23 + (random(-100, 100) / 10000.0);
  data.ndvi = random(100, 900) / 1000.0;
  data.timestamp = millis();
  return data;
}

SensorData readSensors() {
  SensorData data;
  memset(&data, 0, sizeof(data));
  if (useDummyMode) return readDummySensors();

  data.temperature = dht.readTemperature();
  data.humidity = dht.readHumidity();
  if (isnan(data.temperature) || isnan(data.humidity)) {
    Serial.println("DHT read failed");
    data.temperature = -1;
    data.humidity = -1;
  }
  data.soilMoisture = constrain(map(analogRead(SOIL_MOISTURE_PIN), 0, 4095, 100, 0), 0, 100);
  int phRaw = analogRead(PH_SENSOR_PIN);
  data.soilPH = 3.5 + (phRaw / 4095.0) * 7.0;
  data.rainDetected = digitalRead(RAIN_SENSOR_PIN) == LOW;
  data.sunlight = lightMeter.readLightLevel();
  data.latitude = gps.location.isValid() ? gps.location.lat() : 0;
  data.longitude = gps.location.isValid() ? gps.location.lng() : 0;
  data.ndvi = constrain(0.5 + (data.sunlight / 120000.0) * 0.5, 0.0, 1.0);
  data.timestamp = millis();
  return data;
}

void controlPump(bool enable) {
  digitalWrite(RELAY_PIN, enable ? HIGH : LOW);
  Serial.printf("Pump %s\n", enable ? "STARTED" : "STOPPED");
}

void updateDisplay(const SensorData& data, bool connected) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.printf("Temp: %.1f C\n", data.temperature);
  display.printf("Hum:  %.1f %%\n", data.humidity);
  display.printf("Soil: %d %%\n", data.soilMoisture);
  display.printf("pH:   %.1f\n", data.soilPH);
  display.printf("Rain: %s\n", data.rainDetected ? "YES" : "NO");
  display.printf("Light:%.1f lux\n", data.sunlight);
  display.printf("NDVI: %.2f\n", data.ndvi);
  display.setCursor(0, 54);
  display.printf("WiFi: %s", connected ? "OK" : "OFF");
  display.display();
}

bool sendPredictionRequest(const SensorData& data) {
  if (WiFi.status() != WL_CONNECTED) return false;
  http.begin(SERVER_URL);
  http.setTimeout(HTTP_TIMEOUT);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<512> doc;
  doc["region"] = "Auto";
  doc["crop_type"] = "Auto";
  doc["soil_moisture_%"] = data.soilMoisture;
  doc["soil_pH"] = data.soilPH;
  doc["temperature_C"] = data.temperature;
  doc["rainfall_mm"] = data.rainDetected ? 5.0 : 0.0;
  doc["humidity_%"] = data.humidity;
  doc["sunlight_hours"] = data.sunlight / 10000.0;
  doc["irrigation_type"] = "Drip";
  doc["fertilizer_type"] = "Organic";
  doc["pesticide_usage_ml"] = 0;
  doc["total_days"] = 90;
  doc["latitude"] = data.latitude;
  doc["longitude"] = data.longitude;
  doc["NDVI_index"] = data.ndvi;

  String payload;
  serializeJson(doc, payload);
  int httpCode = http.POST(payload);
  http.end();
  return httpCode == 200;
}

void flushOfflineBuffer() {
  if (offlineCount == 0) return;
  Serial.printf("Flushing %d offline records...\n", offlineCount);
  int sent = 0;
  for (int i = 0; i < offlineCount; i++) {
    for (int retry = 0; retry < MAX_RETRIES; retry++) {
      if (sendPredictionRequest(offlineBuffer[i])) { sent++; break; }
      delay(RETRY_DELAY_MS);
    }
  }
  offlineCount = 0;
  Serial.printf("Flushed %d records\n", sent);
}

void bufferOffline(const SensorData& data) {
  if (offlineCount < MAX_OFFLINE_RECORDS) {
    offlineBuffer[offlineCount++] = data;
    Serial.println("Buffered offline");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n===== SMART AGRICULTURE ESP32 =====");
  dht.begin();
  Wire.begin(OLED_SDA, OLED_SCL);
  lightMeter.begin();
  pinMode(SOIL_MOISTURE_PIN, INPUT);
  pinMode(PH_SENSOR_PIN, INPUT);
  pinMode(RAIN_SENSOR_PIN, INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed");
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 20);
  display.println("AgriSense");
  display.println("Booting...");
  display.display();
  delay(1500);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500); Serial.print("."); attempts++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Connected: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi failed - offline mode");
  }
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n'); input.trim();
    if (input == "DUMMY") { useDummyMode = true; Serial.println("Dummy sensor mode enabled"); }
  }
}

void loop() {
  unsigned long now = millis();

  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n'); cmd.trim();
    if (cmd == "DUMMY_ON") { useDummyMode = true; Serial.println("Dummy mode ON"); }
    else if (cmd == "DUMMY_OFF") { useDummyMode = false; Serial.println("Dummy mode OFF"); }
    else if (cmd == "PUMP_ON") { controlPump(true); }
    else if (cmd == "PUMP_OFF") { controlPump(false); }
  }

  if (now - lastSensorRead < SENSOR_INTERVAL_MS) return;
  lastSensorRead = now;

  SensorData data = readSensors();
  bool autoIrrigate = data.soilMoisture < 30 && !data.rainDetected;
  controlPump(autoIrrigate);
  bool wifiOk = WiFi.status() == WL_CONNECTED;
  updateDisplay(data, wifiOk);

  if (wifiOk) {
    flushOfflineBuffer();
    bool sent = false;
    for (int retry = 0; retry < MAX_RETRIES; retry++) {
      if (sendPredictionRequest(data)) { sent = true; break; }
      delay(RETRY_DELAY_MS);
    }
    if (!sent) bufferOffline(data);
  } else {
    bufferOffline(data);
  }

  Serial.printf("Temp:%.1f Hum:%.1f Soil:%d pH:%.1f Rain:%d Lux:%.1f NDVI:%.2f Pump:%d\n",
    data.temperature, data.humidity, data.soilMoisture, data.soilPH,
    data.rainDetected, data.sunlight, data.ndvi, autoIrrigate);
}
