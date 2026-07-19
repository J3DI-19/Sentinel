import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("Sentinel initialization shell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      const response = path.endsWith("/ai")
        ? { service: "ollama", available: false, model_installed: false }
        : { service: path.endsWith("/db") ? "database" : "api", status: "ok" };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200 }));
    }));
  });

  it("renders core and optional service status", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText("database")).toBeInTheDocument());
    expect(screen.getByText("Sentinel")).toBeInTheDocument();
    expect(screen.getAllByText("Ready")).toHaveLength(2);
    expect(screen.getByText("Offline (optional)")).toBeInTheDocument();
  });
});

