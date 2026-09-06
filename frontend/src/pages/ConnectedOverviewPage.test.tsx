import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedOverviewPage } from "./ConnectedOverviewPage";

describe("ConnectedOverviewPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("presents an actionable, structured empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              case_count: 0,
              event_count: 0,
              active_cases: 0,
              recent_cases: [],
            }),
            { status: 200 },
          ),
        ),
      ),
    );
    const navigate = vi.fn();

    render(<ConnectedOverviewPage navigate={navigate} />);

    expect(
      await screen.findByRole("heading", { name: "No persisted cases" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/begin a batch investigation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));
    expect(navigate).toHaveBeenCalledWith("/cases");
  });

  it("uses a keyboard-accessible control for persisted case navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              case_count: 1,
              event_count: 4,
              active_cases: 1,
              recent_cases: [
                {
                  id: 23,
                  name: "A persisted case with a deliberately long readable name",
                  created_at: "2026-09-01T00:00:00Z",
                  updated_at: null,
                },
              ],
            }),
            { status: 200 },
          ),
        ),
      ),
    );
    const navigate = vi.fn();

    render(<ConnectedOverviewPage navigate={navigate} />);

    const caseButton = await screen.findByRole("button", {
      name: "A persisted case with a deliberately long readable name",
    });
    fireEvent.click(caseButton);
    expect(navigate).toHaveBeenCalledWith("/cases/23/overview");
    expect(screen.getByRole("columnheader", { name: "Updated (UTC)" })).toBeInTheDocument();
  });
});
