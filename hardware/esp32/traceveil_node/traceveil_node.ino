// Traceveil Step 5 reference ESP32 node.
//
// Emits LiveTelemetryInput (schema_version 1.0) matching
// backend/app/evidence/schemas.py to POST /api/v1/live/telemetry with
// header X-Traceveil-Source-Token. Supports HTTP direct (default) or MQTT
// via the bridge, with HTTP failover when the broker is silent. Every
// frame carries a strictly monotonic per-node sequence persisted in NVS
// so a reboot does not regress the counter (the replay-detection scenario
// relies on this).
//
// Required libraries (Arduino IDE / arduino-cli):
//   - WiFi (bundled with the ESP32 core)
//   - HTTPClient / WiFiClientSecure (bundled)
//   - PubSubClient (Nick O'Leary) - only if TV_TRANSPORT_MQTT == 1
//   - ArduinoJson (Benoit Blanchon)
//   - DHT sensor library (Adafruit) + Adafruit Unified Sensor
//   - Preferences (bundled)
//   - time.h (bundled)

#include "config.h"

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <DHT.h>
#include <time.h>

#if TV_TRANSPORT_MQTT
#include <PubSubClient.h>
#endif

// -----------------------------------------------------------------------------
// Globals
// -----------------------------------------------------------------------------
static DHT           dht(TV_PIN_DHT, DHT22);
static Preferences   nvs;
static uint32_t      g_sequence          = 0;
static bool          g_relay_state       = false;      // last commanded state
static bool          g_last_motion       = false;
static unsigned long g_last_sample_ms    = 0;
static unsigned long g_last_heartbeat_ms = 0;
static unsigned long g_last_mqtt_ok_ms   = 0;

#if TV_TRANSPORT_MQTT
static WiFiClientSecure mqtt_net;
static PubSubClient     mqtt(mqtt_net);
#endif

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
static void set_status_led(bool on) {
  digitalWrite(TV_PIN_STATUS_LED, on ? HIGH : LOW);
}

static void blink_error(uint8_t times) {
  for (uint8_t i = 0; i < times; ++i) {
    set_status_led(false); delay(120);
    set_status_led(true);  delay(120);
  }
}

static bool wifi_up() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(TV_WIFI_SSID, TV_WIFI_PSK);
  unsigned long deadline = millis() + 15000UL;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) delay(200);
  return WiFi.status() == WL_CONNECTED;
}

// Blocks until NTP has actually stepped the clock. The canonical event
// contract refuses timezone-naive or clearly wrong timestamps.
static bool ntp_ready() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");  // UTC
  time_t now = 0;
  unsigned long deadline = millis() + 15000UL;
  while (millis() < deadline) {
    now = time(nullptr);
    if (now > 1700000000) return true;  // past 2023-11
    delay(200);
  }
  return false;
}

// Formats "YYYY-MM-DDTHH:MM:SS.mmm+00:00" in UTC. observed_at requires an
// explicit offset per the canonical event contract.
static String iso_now_utc() {
  struct timeval tv; gettimeofday(&tv, nullptr);
  struct tm  utc;    gmtime_r(&tv.tv_sec, &utc);
  char buf[40];
  int ms = tv.tv_usec / 1000;
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d.%03d+00:00",
           utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday,
           utc.tm_hour, utc.tm_min, utc.tm_sec, ms);
  return String(buf);
}

static uint32_t next_sequence() {
  ++g_sequence;
  nvs.putUInt("seq", g_sequence);
  return g_sequence;
}

// -----------------------------------------------------------------------------
// Envelope
// -----------------------------------------------------------------------------
static String build_envelope(const char* event_type,
                             const JsonObject& metrics_src) {
  StaticJsonDocument<768> doc;
  doc["schema_version"] = "1.0";
  doc["case_id"]        = (int32_t)TV_CASE_ID;
  doc["source_id"]      = TV_SOURCE_ID;
  doc["device_id"]      = TV_DEVICE_ID;
  doc["event_type"]     = event_type;
  doc["observed_at"]    = iso_now_utc();
  doc["sequence"]       = next_sequence();
  JsonObject metrics    = doc.createNestedObject("metrics");
  for (JsonPairConst kv : metrics_src) metrics[kv.key()] = kv.value();
  String out; serializeJson(doc, out);
  return out;
}

// -----------------------------------------------------------------------------
// Transports
// -----------------------------------------------------------------------------
static bool http_post(const String& body) {
  if (!wifi_up()) return false;
  WiFiClient       plain;
  WiFiClientSecure tls;
  Client* client = nullptr;
  String url;
#if TV_HTTP_TLS
  if (strlen(TV_HTTP_ROOT_CA_PEM) > 0) tls.setCACert(TV_HTTP_ROOT_CA_PEM);
  else tls.setInsecure();  // lab only; supply a pinned cert for anything else
  client = &tls;
  url = String("https://") + TV_HTTP_HOST + ":" + TV_HTTP_PORT + TV_HTTP_PATH;
#else
  client = &plain;
  url = String("http://")  + TV_HTTP_HOST + ":" + TV_HTTP_PORT + TV_HTTP_PATH;
#endif
  HTTPClient http;
  if (!http.begin(*client, url)) return false;
  http.addHeader("Content-Type",             "application/json");
  http.addHeader("X-Traceveil-Source-Token", TV_SOURCE_TOKEN);
  int status = http.POST((uint8_t*)body.c_str(), body.length());
  http.end();
  if (status == 202) return true;
  Serial.printf("http ingest failed: status=%d\n", status);
  return false;
}

#if TV_TRANSPORT_MQTT
static bool mqtt_up() {
  if (mqtt.connected()) return true;
  if (!wifi_up()) return false;
#if TV_MQTT_TLS
  mqtt_net.setInsecure();  // lab only; provision a client cert for production
#endif
  mqtt.setServer(TV_MQTT_HOST, TV_MQTT_PORT);
  const char* status_topic = "tv/dev/" TV_SOURCE_ID "/status";
  bool ok = mqtt.connect(TV_MQTT_CLIENT_ID,
                         /*user*/ nullptr, /*pass*/ nullptr,
                         status_topic, 1, /*retain*/ true,
                         "{\"status\":\"offline\"}");
  if (ok) {
    mqtt.publish(status_topic, "{\"status\":\"online\"}", true);
    g_last_mqtt_ok_ms = millis();
  }
  return ok;
}

static bool mqtt_publish(const String& body) {
  if (!mqtt_up()) return false;
  const char* topic = "tv/dev/" TV_SOURCE_ID "/telemetry";
  bool ok = mqtt.publish(topic, (const uint8_t*)body.c_str(), body.length(), false);
  if (ok) g_last_mqtt_ok_ms = millis();
  return ok;
}
#endif

// Publishes over the preferred transport and falls back to HTTP if MQTT
// looks stalled. This keeps evidence flowing even when the broker or the
// bridge is briefly down; the receipt path is identical either way.
static bool publish(const String& body) {
#if TV_TRANSPORT_MQTT
  if (mqtt_publish(body)) return true;
  if (millis() - g_last_mqtt_ok_ms < TV_MQTT_FAILOVER_MS) return false;
  Serial.println("mqtt stalled; failing over to http");
  return http_post(body);
#else
  return http_post(body);
#endif
}

// -----------------------------------------------------------------------------
// Event emitters
// -----------------------------------------------------------------------------
static void emit_heartbeat() {
  StaticJsonDocument<16> empty;
  JsonObject             metrics = empty.to<JsonObject>();
  String body = build_envelope("heartbeat", metrics);
  if (!publish(body)) blink_error(2);
  g_last_heartbeat_ms = millis();
}

static void emit_telemetry(float temp_c, float humidity_pct, bool motion) {
  StaticJsonDocument<256> doc;
  JsonObject metrics = doc.to<JsonObject>();
  if (!isnan(temp_c))       metrics["temperature_c"] = temp_c;
  if (!isnan(humidity_pct)) metrics["humidity_pct"]  = humidity_pct;
  metrics["motion"]          = motion;
  metrics["relay"]           = g_relay_state ? "on" : "off";
  metrics["battery_voltage"] = 4.82f;  // stub for USB-powered dev kit
  if (temp_c > TV_TEMP_C_ALERT_ABOVE) metrics["threshold_over_temp"] = true;
  String body = build_envelope("telemetry", metrics);
  if (!publish(body)) blink_error(3);
}

static void emit_device_state(const char* key, bool value) {
  StaticJsonDocument<64> doc;
  JsonObject metrics = doc.to<JsonObject>();
  metrics[key] = value;
  String body = build_envelope("device_state", metrics);
  if (!publish(body)) blink_error(3);
}

static void emit_relay_command(bool on) {
  StaticJsonDocument<64> doc;
  JsonObject metrics = doc.to<JsonObject>();
  metrics["target"] = "relay";
  metrics["action"] = on ? "on" : "off";
  String body = build_envelope("command", metrics);
  if (!publish(body)) blink_error(3);
}

// -----------------------------------------------------------------------------
// Setup and loop
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(TV_PIN_STATUS_LED, OUTPUT);
  pinMode(TV_PIN_PIR,   INPUT);
  pinMode(TV_PIN_RELAY, OUTPUT);
  digitalWrite(TV_PIN_RELAY, LOW);
  dht.begin();

  nvs.begin("traceveil", false);
  g_sequence = nvs.getUInt("seq", 0);

  set_status_led(false);
  if (!wifi_up())    { Serial.println("wifi failed"); blink_error(6); }
  if (!ntp_ready())  { Serial.println("ntp failed");  blink_error(6); }
  set_status_led(true);

  // Announce the node so the browser marks the source online.
  emit_heartbeat();
}

void loop() {
#if TV_TRANSPORT_MQTT
  mqtt.loop();
#endif
  unsigned long now = millis();

  // Sample cadence
  if (now - g_last_sample_ms >= TV_SAMPLE_INTERVAL_MS) {
    g_last_sample_ms = now;
    float temp_c       = dht.readTemperature();
    float humidity_pct = dht.readHumidity();
    bool  motion       = digitalRead(TV_PIN_PIR) == HIGH;
    if (motion != g_last_motion) {
      emit_device_state("motion", motion);
      g_last_motion = motion;
    }
    emit_telemetry(temp_c, humidity_pct, motion);
  }

  // Heartbeat cadence (only if the last publish is old enough)
  if (now - g_last_heartbeat_ms >= TV_HEARTBEAT_MS) emit_heartbeat();

  delay(20);
}
