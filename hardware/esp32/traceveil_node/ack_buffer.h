// Traceveil Step 5 - unacked-frame ring buffer (TV5-08 / TV5-09).
//
// Shared between the ESP32 sketch (which instantiates it as
// AckBuffer<Arduino String, TV_ACK_BUFFER_SIZE>) and the native
// tests/step5/ack_buffer_test.cpp (which instantiates it as
// AckBuffer<std::string, 4> and asserts the "buffer full" contract
// the PR #9 re-review required).
//
// Contract, verified by the native test:
//   * track(seq, body) returns true when a slot was available and the
//     frame is now retained; false when every slot is in use.
//   * When track() returns false, the buffer is unchanged and the
//     caller MUST arrange delivery some other way (the sketch's
//     publish() escalates to synchronous HTTPS).
//   * ack(seq) frees the matching slot if any; ack() on an unknown
//     seq is a no-op (does not scramble the buffer).
//   * occupied() reports the number of in_use slots, never more than N.
#pragma once
#include <stddef.h>
#include <stdint.h>

template <typename StringT, size_t N>
class AckBuffer {
public:
  struct Slot {
    uint32_t      sequence;
    unsigned long sent_at_ms;
    StringT       body;
    bool          in_use;
  };

  AckBuffer() {
    for (size_t i = 0; i < N; ++i) { slots_[i].in_use = false; slots_[i].sequence = 0; slots_[i].sent_at_ms = 0; }
  }

  bool track(uint32_t sequence, const StringT& body, unsigned long now_ms) {
    for (size_t i = 0; i < N; ++i) {
      if (!slots_[i].in_use) {
        slots_[i].sequence   = sequence;
        slots_[i].sent_at_ms = now_ms;
        slots_[i].body       = body;
        slots_[i].in_use     = true;
        return true;
      }
    }
    return false;
  }

  bool ack(uint32_t sequence) {
    for (size_t i = 0; i < N; ++i) {
      if (slots_[i].in_use && slots_[i].sequence == sequence) {
        slots_[i].in_use = false;
        slots_[i].body   = StringT();
        return true;
      }
    }
    return false;
  }

  size_t occupied() const {
    size_t n = 0;
    for (size_t i = 0; i < N; ++i) if (slots_[i].in_use) ++n;
    return n;
  }

  static constexpr size_t capacity() { return N; }

  Slot& slot(size_t i) { return slots_[i]; }

private:
  Slot slots_[N];
};
