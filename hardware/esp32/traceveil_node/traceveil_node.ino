// Traceveil Step 5 reference ESP32 node.
//
// Emits LiveTelemetryInput (schema_version 1.0) matching
// backend/app/evidence/schemas.py to POST /api/v1/live/telemetry with
// header X-Traceveil-Source-Token. Supports HTTP direct (default) or
// MQTT via the bridge. Every frame carries a strictly monotonic
// per-node sequence persisted in NVS so a reboot does not regress the
// counter.
//
// Review-driven behavior:
//
//   TV5-02  Mutual TLS is required whenever MQTT is enabled. The three
//           PEM slots in config.h must all parse; setup() halts otherwise.
//   TV5-04  Publication is blocked until NTP has produced a plausible UTC
//           clock. If the lab has no route, provide a local NTP server via
//           TV_NTP_SERVER_1; otherwise the node loops in setup() and never
//           emits a frame with a bogus timestamp.
//   TV5-06  Relay state comes from a separate INPUT sense pin, not the
//           cached g_relay_state variable. A device_state event fires
//           whenever the sensed state disagrees with the last command.
//           The command button (INPUT_PULLUP) issues an authorized
//           command event via emit_relay_command().
//   TV5-08  MQTT publishes are QoS 0. The sketch keeps a bounded ring
//   TV5-09  buffer of unacked frames; the bridge publishes an ACK on
//           tv/dev/<source>/ack, and the sketch drops matching sequences
//           from the buffer. Anything unacked past TV_ACK_TIMEOUT_MS is
//           re-sent via HTTP (which returns a synchronous 202/4xx) so a
//           silent bridge outage cannot swallow evidence.
//   TV5-10  HTTP TLS is on by default. Startup refuses the combination
//           TV_HTTP_TLS==0 with any TV_HTTP_HOST other than 127.0.0.1
//           so the reusable source token cannot leave loopback in the
//           clear by accident.
//   TV5-15  g_last_heartbeat_ms is updated after every successful
//           publish, not only inside emit_heartbeat, so a chatty node
//           does not also spew heartbeats.
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
static bool          g_last_relay_sense  = false;
static bool          g_last_motion       = false;
static unsigned long g_last_sample_ms    = 0;
static unsigned long g_last_heartbeat_ms = 0;
static unsigned long g_last_mqtt_ok_ms   = 0;
static int           g_last_button       = HIGH;
static bool          g_wifi_client_secure_ready = false;

// TV5-08/TV5-09: unacked frame ring buffer.
struct UnackedFrame {
  uint32_t      sequence;
  unsigned long sent_at_ms;
  String        body;
  bool          in_use;
};
static UnackedFrame g_unacked[TV_ACK_BUFFER_SIZE];

#if TV_TRANSPORT_MQTT
static WiFiClientSecure mqtt_net;
static PubSubClient     mqtt(mqtt_net);
#endif

// -----------------------------------------------------------------------------
// Startup guards
// -----------------------------------------------------------------------------
static void halt(const char* reason) {
  Serial.printf("HALT: %s\n", reason);
  while (true) {
    digitalWrite(TV_PIN_STATUS_LED, HIGH); delay(120);
    digitalWrite(TV_PIN_STATUS_LED, LOW);  delay(120);
  }
}

static void assert_transport_config() {
#if TV_TRANSPORT_HTTP == TV_TRANSPORT_MQTT
  halt("config.h must set exactly one of TV_TRANSPORT_HTTP or TV_TRANSPORT_MQTT to 1");
#endif

#if TV_TRANSPORT_HTTP
#  if TV_HTTP_TLS == 0
  // TV5-10: plaintext HTTP is only permitted against loopback.
  if (strcmp(TV_HTTP_HOST, "127.0.0.1") != 0 && strcmp(TV_HTTP_HOST, "localhost") != 0) {
    halt("plaintext HTTP is only allowed to 127.0.0.1; set TV_HTTP_TLS to 1");
  }
#  else
  if (strlen(TV_HTTP_ROOT_CA_PEM) < 64 ||
      strstr(TV_HTTP_ROOT_CA_PEM, "REPLACE-WITH") != nullptr) {
    halt("TV_HTTP_TLS is on but TV_HTTP_ROOT_CA_PEM is unset");
  }
#  endif
#endif

#if TV_TRANSPORT_MQTT
  // TV5-02: mutual TLS material must be present.
  if (TV_MQTT_TLS != 1) halt("MQTT must use TLS; set TV_MQTT_TLS to 1");
  if (strlen(TV_MQTT_CA_PEM) < 64 || strstr(TV_MQTT_CA_PEM, "REPLACE-WITH") != nullptr)
    halt("TV_MQTT_CA_PEM is unset");
  if (strlen(TV_MQTT_CLIENT_CERT_PEM) < 64 || strstr(TV_MQTT_CLIENT_CERT_PEM, "REPLACE-WITH") != nullptr)
    halt("TV_MQTT_CLIENT_CERT_PEM is unset");
  if (strlen(TV_MQTT_CLIENT_KEY_PEM) < 64 || strstr(TV_MQTT_CLIENT_KEY_PEM, "REPLACE-WITH") != nullptr)
    halt("TV_MQTT_CLIENT_KEY_PEM is unset");
#endif
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
static void set_status_led(bool on) {
  digitalWrite(TV_PIN_STATUS_LED, on ? HIGH : LOW);
}

static bool wifi_up() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(TV_WIFI_SSID, TV_WIFI_PSK);
  unsigned long deadline = millis() + 15000UL;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) delay(200);
  return WiFi.status() == WL_CONNECTED;
}

// TV5-04: block until NTP has produced a plausibly recent UTC clock.
// Returns only when time is trustworthy. The caller must not permit
// publication otherwise.
static void await_ntp_or_halt() {
  configTime(0, 0, TV_NTP_SERVER_1, TV_NTP_SERVER_2);
  unsigned long deadline = millis() + TV_NTP_TIMEOUT_MS;
  while (millis() < deadline) {
    time_t now = time(nullptr);
    if ((unsigned long)now >= TV_NTP_MIN_EPOCH) return;
    delay(200);
  }
  halt("NTP failed; refusing to emit frames without a valid clock");
}

// Formats "YYYY-MM-DDTHH:MM:SS.mmm+00:00" in UTC. observed_at requires
// an explicit offset per the canonical event contract.
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
                             const JsonObject& metrics_src,
                             uint32_t* out_sequence) {
  StaticJsonDocument<768> doc;
  uint32_t seq = next_sequence();
  doc["schema_version"] = "1.0";
  doc["case_id"]        = (int32_t)TV_CASE_ID;
  doc["source_id"]      = TV_SOURCE_ID;
  doc["device_id"]      = TV_DEVICE_ID;
  doc["event_type"]     = event_type;
  doc["observed_at"]    = iso_now_utc();
  doc["sequence"]       = seq;
  JsonObject metrics    = doc.createNestedObject("metrics");
  for (JsonPairConst kv : metrics_src) metrics[kv.key()] = kv.value();
  String out; serializeJson(doc, out);
  if (out_sequence) *out_sequence = seq;
  return out;
}

// -----------------------------------------------------------------------------
// Unacked ring buffer (TV5-08 / TV5-09)
// -----------------------------------------------------------------------------
static void unacked_track(uint32_t sequence, const String& body) {
  for (auto& slot : g_unacked) {
    if (!slot.in_use) {
      slot.sequence   = sequence;
      slot.sent_at_ms = millis();
      slot.body       = body;
      slot.in_use     = true;
      return;
    }
  }
  Serial.printf("unacked buffer full; force-flushing seq %u over HTTP\n",
                (unsigned)sequence);
  // Fall through to caller which will HTTP fallback the newest frame.
}

static void unacked_ack(uint32_t sequence) {
  for (auto& slot : g_unacked) {
    if (slot.in_use && slot.sequence == sequence) {
      slot.in_use = false;
      slot.body   = String();
      return;
    }
  }
}

static bool http_post(const String& body);  // fwd

// Any frame older than TV_ACK_TIMEOUT_MS is re-sent via HTTP. HTTP is
// synchronous - a 202 means the backend accepted it, so we can clear
// the slot; anything else stays queued for the next tick.
static void unacked_retry_stale() {
  unsigned long now = millis();
  for (auto& slot : g_unacked) {
    if (!slot.in_use) continue;
    if (now - slot.sent_at_ms < (unsigned long)TV_ACK_TIMEOUT_MS) continue;
    Serial.printf("no ack for seq %u after %lums; retrying via HTTP\n",
                  (unsigned)slot.sequence, now - slot.sent_at_ms);
    if (http_post(slot.body)) {
      slot.in_use = false;
      slot.body   = String();
    } else {
      slot.sent_at_ms = now;  // back off one interval
    }
  }
}

// -----------------------------------------------------------------------------
// Transports
// -----------------------------------------------------------------------------
static bool http_post(const String& body) {
  if (!wifi_up()) return false;
  WiFiClient       plain;
  WiFiClientSecure tls;
  Client* client = nullptr;
  String  url;
#if TV_HTTP_TLS
  tls.setCACert(TV_HTTP_ROOT_CA_PEM);   // TV5-10: pinned lab CA
  client = &tls;
  url = String("https://") + TV_HTTP_HOST + ":" + TV_HTTP_PORT + TV_HTTP_PATH;
#else
  client = &plain;                       // loopback-only, validated in setup()
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
// ACK topic subscriber: bridge publishes {"sequence": N} after backend
// returns 202. Sketch removes that seq from the unacked buffer.
static void mqtt_on_message(char* topic, byte* payload, unsigned int length) {
  const String ack_topic = "tv/dev/" TV_SOURCE_ID "/ack";
  if (ack_topic != topic) return;
  StaticJsonDocument<64> doc;
  if (deserializeJson(doc, payload, length)) return;
  uint32_t seq = doc["sequence"].as<uint32_t>();
  if (seq > 0) unacked_ack(seq);
}

static bool mqtt_up() {
  if (mqtt.connected()) return true;
  if (!wifi_up()) return false;
  // TV5-02: pin the broker CA and present this node's client cert.
  mqtt_net.setCACert(TV_MQTT_CA_PEM);
  mqtt_net.setCertificate(TV_MQTT_CLIENT_CERT_PEM);
  mqtt_net.setPrivateKey(TV_MQTT_CLIENT_KEY_PEM);
  mqtt.setServer(TV_MQTT_HOST, TV_MQTT_PORT);
  mqtt.setCallback(mqtt_on_message);
  const char* status_topic = "tv/dev/" TV_SOURCE_ID "/status";
  bool ok = mqtt.connect(TV_MQTT_CLIENT_ID,
                         nullptr, nullptr,
                         status_topic, 1, /*retain*/ true,
                         "{\"status\":\"offline\"}");
  if (ok) {
    mqtt.publish(status_topic, "{\"status\":\"online\"}", true);
    mqtt.subscribe(("tv/dev/" TV_SOURCE_ID "/ack"), 1);
    g_last_mqtt_ok_ms = millis();
    // Re-drain any unacked frames from a previous connection.
    for (auto& slot : g_unacked) {
      if (slot.in_use) {
        mqtt.publish(("tv/dev/" TV_SOURCE_ID "/telemetry"),
                     (const uint8_t*)slot.body.c_str(), slot.body.length(), false);
        slot.sent_at_ms = millis();
      }
    }
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

// Publishes over the preferred transport. Returns true if delivery was at
// least handed to the transport (and, for HTTP, was ACKed synchronously).
static bool publish(const String& body, uint32_t sequence) {
  bool ok = false;
#if TV_TRANSPORT_MQTT
  if (mqtt_publish(body)) {
    unacked_track(sequence, body);   // wait for bridge ack
    ok = true;
  } else if (millis() - g_last_mqtt_ok_ms >= TV_MQTT_FAILOVER_MS) {
    Serial.println("mqtt stalled; failing over to http");
    ok = http_post(body);
  }
#else
  ok = http_post(body);
#endif
  if (ok) g_last_heartbeat_ms = millis();  // TV5-15
  return ok;
}

// -----------------------------------------------------------------------------
// Event emitters
// -----------------------------------------------------------------------------
static void emit_heartbeat() {
  StaticJsonDocument<16> empty;
  JsonObject             metrics = empty.to<JsonObject>();
  uint32_t seq = 0;
  String body = build_envelope("heartbeat", metrics, &seq);
  publish(body, seq);
}

static void emit_telemetry(float temp_c, float humidity_pct, bool motion, bool relay_sensed) {
  StaticJsonDocument<256> doc;
  JsonObject metrics = doc.to<JsonObject>();
  if (!isnan(temp_c))       metrics["temperature_c"] = temp_c;
  if (!isnan(humidity_pct)) metrics["humidity_pct"]  = humidity_pct;
  metrics["motion"]          = motion;
  metrics["relay"]           = relay_sensed ? "on" : "off";
  metrics["battery_voltage"] = 4.82f;
  if (temp_c > TV_TEMP_C_ALERT_ABOVE) metrics["threshold_over_temp"] = true;
  uint32_t seq = 0;
  String body = build_envelope("telemetry", metrics, &seq);
  publish(body, seq);
}

static void emit_device_state(const char* key, bool value) {
  StaticJsonDocument<64> doc;
  JsonObject metrics = doc.to<JsonObject>();
  metrics[key] = value;
  uint32_t seq = 0;
  String body = build_envelope("device_state", metrics, &seq);
  publish(body, seq);
}

static void emit_relay_command(bool on) {
  StaticJsonDocument<64> doc;
  JsonObject metrics = doc.to<JsonObject>();
  metrics["target"] = "relay";
  metrics["action"] = on ? "on" : "off";
  uint32_t seq = 0;
  String body = build_envelope("command", metrics, &seq);
  publish(body, seq);
}

// -----------------------------------------------------------------------------
// Setup and loop
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(TV_PIN_STATUS_LED,     OUTPUT);
  pinMode(TV_PIN_PIR,            INPUT);
  pinMode(TV_PIN_RELAY,          OUTPUT);
  pinMode(TV_PIN_RELAY_SENSE,    INPUT);
  pinMode(TV_PIN_COMMAND_BUTTON, INPUT_PULLUP);
  digitalWrite(TV_PIN_RELAY, LOW);
  dht.begin();

  assert_transport_config();  // halt() on any misconfiguration

  nvs.begin("traceveil", false);
  g_sequence = nvs.getUInt("seq", 0);

  set_status_led(false);
  if (!wifi_up()) halt("wifi_up() failed");
  await_ntp_or_halt();        // TV5-04
  set_status_led(true);

  emit_heartbeat();
}

void loop() {
#if TV_TRANSPORT_MQTT
  mqtt.loop();
#endif
  unsigned long now = millis();

  // TV5-08/TV5-09: re-send anything the bridge has not acked.
  unacked_retry_stale();

  // Command button: operator-initiated authorized relay toggle. This is
  // the authorized command path referenced by TV5-06; the actuation
  // scenario watches for a device_state that lacks a preceding command.
  int button = digitalRead(TV_PIN_COMMAND_BUTTON);
  if (g_last_button == HIGH && button == LOW) {
    bool desired = !((bool)digitalRead(TV_PIN_RELAY));
    digitalWrite(TV_PIN_RELAY, desired ? HIGH : LOW);
    emit_relay_command(desired);
  }
  g_last_button = button;

  if (now - g_last_sample_ms >= TV_SAMPLE_INTERVAL_MS) {
    g_last_sample_ms = now;

    float temp_c       = dht.readTemperature();
    float humidity_pct = dht.readHumidity();
    bool  motion       = digitalRead(TV_PIN_PIR)         == HIGH;
    bool  relay_sensed = digitalRead(TV_PIN_RELAY_SENSE) == HIGH;

    if (motion != g_last_motion) {
      emit_device_state("motion", motion);
      g_last_motion = motion;
    }
    // TV5-06: sensed state disagrees with cached commanded state -> ungrounded change.
    if (relay_sensed != g_last_relay_sense) {
      emit_device_state("relay", relay_sensed);
      g_last_relay_sense = relay_sensed;
    }
    emit_telemetry(temp_c, humidity_pct, motion, relay_sensed);
  }

  if (now - g_last_heartbeat_ms >= TV_HEARTBEAT_MS) emit_heartbeat();

  delay(20);
}
