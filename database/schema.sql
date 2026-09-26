-- Smart Agriculture Database Schema

CREATE DATABASE IF NOT EXISTS smart_agriculture
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smart_agriculture;

-- ===================== USERS =====================

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(120) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin', 'user') DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_email (email),
  INDEX idx_users_username (username)
) ENGINE=InnoDB;

-- ===================== PREDICTION HISTORY =====================

CREATE TABLE IF NOT EXISTS prediction_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT DEFAULT NULL,
  region VARCHAR(100) DEFAULT NULL,
  crop_type VARCHAR(100) DEFAULT NULL,
  soil_moisture DECIMAL(6,2) DEFAULT NULL,
  soil_ph DECIMAL(4,2) DEFAULT NULL,
  temperature DECIMAL(5,2) DEFAULT NULL,
  rainfall DECIMAL(7,2) DEFAULT NULL,
  humidity DECIMAL(5,2) DEFAULT NULL,
  sunlight_hours DECIMAL(5,2) DEFAULT NULL,
  irrigation_type VARCHAR(50) DEFAULT NULL,
  fertilizer_type VARCHAR(50) DEFAULT NULL,
  pesticide_usage DECIMAL(8,2) DEFAULT NULL,
  total_days INT DEFAULT NULL,
  latitude DECIMAL(10,7) DEFAULT NULL,
  longitude DECIMAL(10,7) DEFAULT NULL,
  ndvi_index DECIMAL(5,4) DEFAULT NULL,
  crop_recommendation VARCHAR(100) DEFAULT NULL,
  predicted_yield DECIMAL(10,2) DEFAULT NULL,
  disease_prediction VARCHAR(100) DEFAULT NULL,
  heat_stress VARCHAR(50) DEFAULT NULL,
  soil_health VARCHAR(50) DEFAULT NULL,
  fertilizer_recommendation VARCHAR(100) DEFAULT NULL,
  irrigation_time VARCHAR(50) DEFAULT NULL,
  rain_impact VARCHAR(50) DEFAULT NULL,
  farm_efficiency VARCHAR(50) DEFAULT NULL,
  confidence VARCHAR(10) DEFAULT NULL,
  model_version VARCHAR(20) DEFAULT 'v1.0',
  prediction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_history_user (user_id),
  INDEX idx_history_region (region),
  INDEX idx_history_crop (crop_type),
  INDEX idx_history_time (prediction_time),
  INDEX idx_history_recommendation (crop_recommendation),
  INDEX idx_history_disease (disease_prediction)
) ENGINE=InnoDB;

-- ===================== SETTINGS =====================

CREATE TABLE IF NOT EXISTS user_settings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNIQUE NOT NULL,
  theme ENUM('light', 'dark', 'system') DEFAULT 'system',
  language VARCHAR(10) DEFAULT 'en',
  units ENUM('metric', 'imperial') DEFAULT 'metric',
  notifications_enabled BOOLEAN DEFAULT TRUE,
  notify_heat BOOLEAN DEFAULT TRUE,
  notify_rain BOOLEAN DEFAULT TRUE,
  notify_disease BOOLEAN DEFAULT TRUE,
  notify_soil BOOLEAN DEFAULT TRUE,
  notify_irrigation BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ===================== WEATHER CACHE =====================

CREATE TABLE IF NOT EXISTS weather_cache (
  id INT AUTO_INCREMENT PRIMARY KEY,
  latitude DECIMAL(10,7) NOT NULL,
  longitude DECIMAL(10,7) NOT NULL,
  weather_data JSON DEFAULT NULL,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_location (latitude, longitude),
  INDEX idx_weather_fetched (fetched_at)
) ENGINE=InnoDB;

-- ===================== AUDIT LOGS =====================

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT DEFAULT NULL,
  action VARCHAR(50) NOT NULL,
  entity_type VARCHAR(50) DEFAULT NULL,
  entity_id INT DEFAULT NULL,
  details JSON DEFAULT NULL,
  ip_address VARCHAR(45) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_logs_user (user_id),
  INDEX idx_logs_action (action),
  INDEX idx_logs_created (created_at),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ===================== FIELD DEVICES (v2) =====================
-- Each ESP32 node is registered with its farm context so it never has to
-- guess region/crop. Only a SHA-256 hash of the device key is stored.

CREATE TABLE IF NOT EXISTS devices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  device_uid VARCHAR(32) UNIQUE NOT NULL,
  api_key_hash CHAR(64) UNIQUE NOT NULL,
  owner_user_id INT DEFAULT NULL,
  name VARCHAR(100) NOT NULL,
  crop VARCHAR(50) NOT NULL,
  sowing_date DATE NOT NULL,
  soil_texture VARCHAR(30) NOT NULL,
  area_m2 DECIMAL(12,2) NOT NULL,
  irrigation_method VARCHAR(20) NOT NULL DEFAULT 'drip',
  latitude DECIMAL(10,7) DEFAULT NULL,
  longitude DECIMAL(10,7) DEFAULT NULL,
  elevation_m DECIMAL(7,1) DEFAULT 0,
  pump_flow_lph DECIMAL(10,2) DEFAULT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_devices_owner (owner_user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sensor_readings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  device_id INT NOT NULL,
  soil_vwc_pct DECIMAL(5,2) DEFAULT NULL,
  air_temp_c DECIMAL(5,2) DEFAULT NULL,
  air_rh_pct DECIMAL(5,2) DEFAULT NULL,
  rain_mm DECIMAL(6,2) DEFAULT NULL,
  battery_v DECIMAL(4,2) DEFAULT NULL,
  firmware VARCHAR(20) DEFAULT NULL,
  received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
  INDEX idx_readings_device_time (device_id, received_at)
) ENGINE=InnoDB;
