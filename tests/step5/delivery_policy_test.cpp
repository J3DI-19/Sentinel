// Native test for hardware/esp32/traceveil_node/delivery_policy.h (TV5-09).
//
// Exercises the five frame-loss scenarios from the PR #9 re-review with
// fake transports, so no board or network is required.
//
// Build: g++ -std=c++17 delivery_policy_test.cpp -o delivery_policy_test
// Run:   ./delivery_policy_test   (exit 0 = pass)

#include "../../hardware/esp32/traceveil_node/delivery_policy.h"

#include <cstdio>
#include <string>

static int failures = 0;
#define REQUIRE(cond) do {                                                    \
    if (!(cond)) { std::fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #cond); ++failures; } \
  } while (0)

using Buf = AckBuffer<std::string, 4>;

static void fill(Buf& b, unsigned long now) {
  for (uint32_t s = 1; s <= 4; ++s) REQUIRE(b.track(s, "old", now));
  REQUIRE(b.full());
}

int main() {
  // --- Scenario 3: MQTT fails within grace period -> frame retained -------
  {
    Buf b;
    auto mqtt_down = [] { return false; };
    auto http_down = [] { return false; };
    auto o = deliver_mqtt_mode(b, 10, std::string("f"), mqtt_down, http_down, 100);
    REQUIRE(o == DeliveryOutcome::QUEUED_PENDING);
    REQUIRE(delivery_no_loss(o));
    REQUIRE(b.occupied() == 1);          // frame is queued, not discarded
  }

  // --- Scenario 4: MQTT and HTTP both unavailable -> frame retained -------
  {
    Buf b;
    auto o = deliver_mqtt_mode(b, 11, std::string("f"),
                               [] { return false; }, [] { return false; }, 100);
    REQUIRE(o == DeliveryOutcome::QUEUED_PENDING);
    REQUIRE(b.occupied() == 1);
  }

  // --- MQTT success -> tracked, awaiting ACK ------------------------------
  {
    Buf b;
    auto o = deliver_mqtt_mode(b, 12, std::string("f"),
                               [] { return true; }, [] { return false; }, 100);
    REQUIRE(o == DeliveryOutcome::QUEUED_MQTT);
    REQUIRE(b.occupied() == 1);
  }

  // --- MQTT down but HTTP up -> delivered synchronously, slot freed -------
  {
    Buf b;
    auto o = deliver_mqtt_mode(b, 13, std::string("f"),
                               [] { return false; }, [] { return true; }, 100);
    REQUIRE(o == DeliveryOutcome::DELIVERED_HTTP);
    REQUIRE(b.occupied() == 0);          // not left in the buffer
  }

  // --- Scenario 1: full buffer + successful HTTP fallback -----------------
  {
    Buf b; fill(b, 50);
    auto o = deliver_mqtt_mode(b, 99, std::string("new"),
                               [] { return true; }, [] { return true; }, 100);
    // Buffer was full, so MQTT is not even attempted; HTTP succeeds.
    REQUIRE(o == DeliveryOutcome::DELIVERED_HTTP);
    REQUIRE(b.occupied() == 4);          // the four old frames are untouched
  }

  // --- Scenario 2: full buffer + failed HTTP -> drop oldest, keep newest --
  {
    Buf b;
    b.track(1, "oldest", 10);
    b.track(2, "second", 20);
    b.track(3, "third",  30);
    b.track(4, "fourth", 40);
    REQUIRE(b.full());
    auto o = deliver_mqtt_mode(b, 99, std::string("newest"),
                               [] { return true; }, [] { return false; }, 100);
    REQUIRE(o == DeliveryOutcome::DROPPED_OLDEST);
    REQUIRE(!delivery_no_loss(o));       // caller must count this as a loss
    REQUIRE(b.occupied() == 4);
    // Oldest (seq 1) must be gone; newest (seq 99) must be present.
    bool has_oldest = false, has_newest = false;
    for (size_t i = 0; i < Buf::capacity(); ++i) {
      auto& s = b.slot(i);
      if (!s.in_use) continue;
      if (s.sequence == 1)  has_oldest = true;
      if (s.sequence == 99) has_newest = true;
    }
    REQUIRE(!has_oldest);
    REQUIRE(has_newest);
  }

  // --- HTTP-only mode: success -> not tracked -----------------------------
  {
    Buf b;
    auto o = deliver_http_mode(b, 20, std::string("f"), [] { return true; }, 100);
    REQUIRE(o == DeliveryOutcome::DELIVERED_HTTP);
    REQUIRE(b.occupied() == 0);
  }

  // --- HTTP-only mode: failure -> retained for retry ----------------------
  {
    Buf b;
    auto o = deliver_http_mode(b, 21, std::string("f"), [] { return false; }, 100);
    REQUIRE(o == DeliveryOutcome::QUEUED_PENDING);
    REQUIRE(b.occupied() == 1);
  }

  // --- HTTP-only mode: failure + full buffer -> drop oldest, keep newest --
  {
    Buf b;
    b.track(1, "oldest", 10); b.track(2, "b", 20); b.track(3, "c", 30); b.track(4, "d", 40);
    auto o = deliver_http_mode(b, 77, std::string("newest"), [] { return false; }, 100);
    REQUIRE(o == DeliveryOutcome::DROPPED_OLDEST);
    bool has_oldest = false, has_newest = false;
    for (size_t i = 0; i < Buf::capacity(); ++i) {
      auto& s = b.slot(i);
      if (s.in_use && s.sequence == 1)  has_oldest = true;
      if (s.in_use && s.sequence == 77) has_newest = true;
    }
    REQUIRE(!has_oldest);
    REQUIRE(has_newest);
  }

  if (failures == 0) { std::printf("delivery_policy_test: OK\n"); return 0; }
  std::fprintf(stderr, "delivery_policy_test: %d failure(s)\n", failures);
  return 1;
}
