// Traceveil Step 5 - transport-agnostic delivery policy (TV5-09).
//
// The frame-loss-prevention logic is factored out of the sketch so it
// can be unit-tested natively (tests/step5/delivery_policy_test.cpp)
// against fake transports, covering the five scenarios the PR #9
// re-review required:
//   1. full buffer + successful HTTP fallback
//   2. full buffer + failed HTTP fallback (oldest dropped, newest kept)
//   3. MQTT failure inside the failover grace period (frame retained)
//   4. MQTT and HTTP both unavailable (frame retained)
//   5. exact behavior is deterministic and independent of wall-clock
//
// Contract:
//   * Every frame is QUEUED in the ack buffer BEFORE MQTT is attempted,
//     so a frame is never lost merely because MQTT publish returned
//     false (including during the failover grace period).
//   * When the buffer is full, a synchronous HTTP delivery is attempted;
//     only if that ALSO fails is a frame dropped, and then it is the
//     OLDEST un-acked frame, never the newest - and the outcome is
//     reported as DROPPED_OLDEST so the caller can log/count the loss.
//   * Frames delivered synchronously over HTTP are removed from the
//     buffer (their slot is freed) so they are not retried.
//
// Remaining loss condition (documented, not eliminated): frames still
// sitting un-acked in the RAM buffer are lost on a hard power cut,
// because the buffer is not persisted to NVS. The node therefore does
// NOT claim guaranteed delivery across power loss.
#pragma once
#include "ack_buffer.h"

enum class DeliveryOutcome {
  DELIVERED_HTTP,   // sent synchronously over HTTP; slot freed
  QUEUED_MQTT,      // published to MQTT and tracked; awaiting bridge ACK
  QUEUED_PENDING,   // transport unavailable now; retained in buffer for retry
  DROPPED_OLDEST,   // buffer full and HTTP down: newest queued, oldest un-acked dropped
};

// MQTT-preferred delivery. try_mqtt() publishes to the broker (true on
// success); try_http() performs a synchronous HTTPS POST (true on 202).
template <typename Buf, typename TryMqtt, typename TryHttp>
DeliveryOutcome deliver_mqtt_mode(Buf& buf, uint32_t seq, const typename Buf::BodyType& body,
                                  TryMqtt try_mqtt, TryHttp try_http, unsigned long now) {
  if (buf.track(seq, body, now)) {
    if (try_mqtt()) return DeliveryOutcome::QUEUED_MQTT;
    // MQTT unavailable. The frame is already safely queued (it will be
    // retried by the stale-retry loop), but attempt HTTP now to minimise
    // latency; on success, free the slot.
    if (try_http()) { buf.ack(seq); return DeliveryOutcome::DELIVERED_HTTP; }
    return DeliveryOutcome::QUEUED_PENDING;
  }
  // Buffer full: synchronous HTTP, else drop the oldest to keep the newest.
  if (try_http()) return DeliveryOutcome::DELIVERED_HTTP;
  buf.evict_oldest();
  buf.track(seq, body, now);
  return DeliveryOutcome::DROPPED_OLDEST;
}

// HTTP-only delivery (no broker). There is no ACK channel, so a frame is
// tracked only when the synchronous POST fails, to be retried later.
template <typename Buf, typename TryHttp>
DeliveryOutcome deliver_http_mode(Buf& buf, uint32_t seq, const typename Buf::BodyType& body,
                                  TryHttp try_http, unsigned long now) {
  if (try_http()) return DeliveryOutcome::DELIVERED_HTTP;
  if (buf.track(seq, body, now)) return DeliveryOutcome::QUEUED_PENDING;
  buf.evict_oldest();
  buf.track(seq, body, now);
  return DeliveryOutcome::DROPPED_OLDEST;
}

// Convenience: did this outcome leave the frame safely handled (delivered
// or retained), i.e. no frame was lost on this call?
inline bool delivery_no_loss(DeliveryOutcome o) {
  return o != DeliveryOutcome::DROPPED_OLDEST;
}
