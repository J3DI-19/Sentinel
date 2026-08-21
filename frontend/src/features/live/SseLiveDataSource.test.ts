import { describe, expect, it, vi } from "vitest";
import { SseLiveDataSource, type ConnectionState } from "./SseLiveDataSource";

describe("SseLiveDataSource", () => {
  it("parses typed envelopes, reports malformed messages, and cleans up on abort", async () => {
    const controller = new AbortController(); const states: ConnectionState[] = []; const messages: unknown[] = []; const errors: string[] = [];
    const encoded = new TextEncoder().encode('id: 42\nevent: event.accepted\ndata: {"schema_version":"1.0","id":42,"topic":"event.accepted","payload":{"event_id":"EV-42"}}\n\ndata: not-json\n\n');
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new ReadableStream({ start(stream) { stream.enqueue(encoded); } }), { status: 200 })));
    const source = new SseLiveDataSource();
    await source.connect({ caseId: 7, signal: controller.signal, onState: state => states.push(state), onMessage: message => { messages.push(message); controller.abort(); }, onError: message => errors.push(message) });
    expect(states).toEqual(["connecting", "connected", "disconnected"]);
    expect(messages).toEqual([expect.objectContaining({ id: 42, topic: "event.accepted" })]);
    expect(errors).toContain("A malformed stream message was ignored.");
  });

  it("stops with a terminal error for non-retryable client responses", async () => {
    const states: ConnectionState[] = []; const errors: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 401 })));
    await new SseLiveDataSource().connect({ caseId: 7, signal: new AbortController().signal, onState: state => states.push(state), onMessage: () => undefined, onError: message => errors.push(message) });
    expect(states).toEqual(["connecting", "terminal-error"]);
    expect(errors[0]).toContain("401");
  });
});
