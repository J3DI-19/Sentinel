// CI-only config.h for arduino-cli compile. Values are stubs and are
// never flashed to hardware. The one real requirement is that the file
// compiles cleanly against traceveil_node.ino with every startup guard
// (TV5-02, TV5-04, TV5-10) present.
#pragma once

#define TV_WIFI_SSID        "ci-noop"
#define TV_WIFI_PSK         "ci-noop"

#define TV_CASE_ID          1
#define TV_SOURCE_ID        "esp32-ci-01"
#define TV_DEVICE_ID        "esp32-ci-01"
#define TV_SOURCE_TOKEN     "ci-noop"

// Loopback + plaintext is the ONE combination TV5-10 permits without
// pinned CA material. Anything else would need a full PEM below.
#define TV_TRANSPORT_HTTP   1
#define TV_TRANSPORT_MQTT   0
#define TV_HTTP_HOST        "127.0.0.1"
#define TV_HTTP_PORT        8000
#define TV_HTTP_PATH        "/api/v1/live/telemetry"
#define TV_HTTP_TLS         0
static const char TV_HTTP_ROOT_CA_PEM[] = "";

#define TV_MQTT_HOST                "127.0.0.1"
#define TV_MQTT_PORT                8883
#define TV_MQTT_CLIENT_ID           TV_SOURCE_ID
#define TV_MQTT_TLS                 1
static const char TV_MQTT_CA_PEM[]          = "";
static const char TV_MQTT_CLIENT_CERT_PEM[] = "";
static const char TV_MQTT_CLIENT_KEY_PEM[]  = "";

#define TV_ACK_BUFFER_SIZE          8
#define TV_ACK_TIMEOUT_MS           6000
#define TV_MQTT_FAILOVER_MS         4000

#define TV_NTP_SERVER_1             "127.0.0.1"
#define TV_NTP_SERVER_2             "127.0.0.1"
#define TV_NTP_MIN_EPOCH            1735689600UL
#define TV_NTP_TIMEOUT_MS           1000

#define TV_SAMPLE_INTERVAL_MS       3000
#define TV_HEARTBEAT_MS             15000

#define TV_PIN_DHT                  4
#define TV_PIN_PIR                  27
#define TV_PIN_RELAY                26
#define TV_PIN_RELAY_SENSE          25
#define TV_PIN_COMMAND_BUTTON       33
#define TV_PIN_STATUS_LED           2

#define TV_TEMP_C_ALERT_ABOVE       32.0f
