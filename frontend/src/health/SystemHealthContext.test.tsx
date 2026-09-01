import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

afterEach(() => vi.unstubAllGlobals());

function responseFor(path: string, databaseStatus = "ok") {
  const body = path.endsWith("/ai")
    ? { service: "ollama", available: false, model_installed: false }
    : { service: path.endsWith("/db") ? "database" : "api", status: path.endsWith("/db") ? databaseStatus : "ok" };
  return new Response(JSON.stringify(body), { status: 200 });
}

describe("shared system health", () => {
  it("keeps optional Ollama offline while core systems remain operational", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => Promise.resolve(responseFor(String(input)))));
    window.history.replaceState({}, "", "/status");
    render(<App/>);
    expect(await screen.findByRole("button", { name: "Platform health: operational" })).toBeInTheDocument();
    expect(screen.getByText("Optional offline")).toBeInTheDocument();
  });

  it("distinguishes database and backend outages", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => Promise.resolve(responseFor(String(input), "unavailable"))));
    window.history.replaceState({}, "", "/status");
    const { unmount } = render(<App/>);
    expect(await screen.findByRole("button", { name: "Platform health: database unavailable" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Evidence database unavailable");
    unmount();

    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    render(<App/>);
    expect(await screen.findByRole("button", { name: "Platform health: backend unavailable" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Backend API unavailable");
  });

  it("refreshes shared status without reloading the browser", async () => {
    let databaseChecks = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/db")) databaseChecks += 1;
      return Promise.resolve(responseFor(path, databaseChecks === 1 ? "unavailable" : "ok"));
    }));
    window.history.replaceState({}, "", "/status");
    render(<App/>);
    await screen.findByRole("button", { name: "Platform health: database unavailable" });
    fireEvent.click(screen.getByRole("button", { name: /Refresh status/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Platform health: operational" })).toBeInTheDocument());
  });
});
