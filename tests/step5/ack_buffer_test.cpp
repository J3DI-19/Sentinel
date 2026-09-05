// Native test for hardware/esp32/traceveil_node/ack_buffer.h.
//
// The PR #9 re-review required "a test that covers a full ACK buffer
// and proves the next frame is not lost." The sketch's publish()
// treats track()==false as a signal to escalate delivery to
// synchronous HTTPS, so the invariant this file must guarantee is
// simply: when N slots are in_use, the (N+1)th track() call MUST
// return false rather than silently accepting the frame.
//
// Build: g++ -std=c++17 ack_buffer_test.cpp -o ack_buffer_test
// Run:   ./ack_buffer_test    (exits 0 on pass, non-zero on fail)

#include "../../hardware/esp32/traceveil_node/ack_buffer.h"

#include <cassert>
#include <cstdio>
#include <string>

static int failures = 0;

#define REQUIRE(cond) do {                                                    \
    if (!(cond)) {                                                            \
      std::fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #cond);     \
      ++failures;                                                             \
    }                                                                         \
  } while (0)

int main() {
  using Buf = AckBuffer<std::string, 4>;

  // --- fresh buffer accepts up to N frames ----------------------------------
  {
    Buf b;
    REQUIRE(b.occupied() == 0);
    REQUIRE(b.track(1, "one",   1000));
    REQUIRE(b.track(2, "two",   1001));
    REQUIRE(b.track(3, "three", 1002));
    REQUIRE(b.track(4, "four",  1003));
    REQUIRE(b.occupied() == 4);

    // (N+1)-th track MUST return false.
    REQUIRE(!b.track(5, "five", 1004));
    REQUIRE(b.occupied() == 4);

    // And the buffer must be UNCHANGED: none of the four existing
    // sequences was overwritten to make room for the fifth.
    int found = 0;
    for (size_t i = 0; i < Buf::capacity(); ++i) {
      auto& s = b.slot(i);
      if (!s.in_use) continue;
      switch (s.sequence) {
        case 1: REQUIRE(s.body == "one");   ++found; break;
        case 2: REQUIRE(s.body == "two");   ++found; break;
        case 3: REQUIRE(s.body == "three"); ++found; break;
        case 4: REQUIRE(s.body == "four");  ++found; break;
        default: REQUIRE(false); break;
      }
    }
    REQUIRE(found == 4);
  }

  // --- ack() frees a slot; next track() must then succeed --------------------
  {
    Buf b;
    for (uint32_t s = 10; s < 14; ++s) REQUIRE(b.track(s, "x", 0));
    REQUIRE(!b.track(99, "overflow", 0));   // full: rejected

    REQUIRE(b.ack(12));                     // free slot for seq 12
    REQUIRE(b.occupied() == 3);

    REQUIRE(b.track(99, "now-fits", 0));    // slot available again
    REQUIRE(b.occupied() == 4);
  }

  // --- ack() on unknown sequence is a no-op ---------------------------------
  {
    Buf b;
    b.track(1, "a", 0);
    b.track(2, "b", 0);
    REQUIRE(!b.ack(999));
    REQUIRE(b.occupied() == 2);
  }

  // --- ack() twice on the same sequence: first frees, second no-op ----------
  {
    Buf b;
    b.track(7, "seven", 0);
    REQUIRE(b.ack(7));
    REQUIRE(!b.ack(7));
    REQUIRE(b.occupied() == 0);
  }

  if (failures == 0) {
    std::printf("ack_buffer_test: OK\n");
    return 0;
  }
  std::fprintf(stderr, "ack_buffer_test: %d failure(s)\n", failures);
  return 1;
}
