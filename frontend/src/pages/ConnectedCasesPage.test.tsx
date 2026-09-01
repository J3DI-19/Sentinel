import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedCasesPage } from "./ConnectedCasesPage";

const page = { items: [], page: 1, page_size: 100, total: 0 };
const created = { id: 42, name: "Review case", description: "Batch showcase", case_type: "batch", status: "active", owner: "Reviewer", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };

describe("ConnectedCasesPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("creates a persisted case with an inline form and opens import with its ID", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => Promise.resolve(new Response(JSON.stringify(init?.method === "POST" ? created : page), { status: init?.method === "POST" ? 201 : 200 })));
    vi.stubGlobal("fetch", fetchMock);
    const navigate = vi.fn();
    render(<ConnectedCasesPage navigate={navigate}/>);
    expect(await screen.findByText("No persisted cases")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));
    fireEvent.change(screen.getByLabelText("Case name"), { target: { value: "  Review case  " } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "  Batch showcase  " } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "  Reviewer  " } });
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/import?case=42"));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ name: "Review case", description: "Batch showcase", owner: "Reviewer" });
  });

  it("keeps form values after a failed request and blocks duplicate submission", async () => {
    let resolvePost: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => init?.method === "POST"
      ? new Promise<Response>(resolve => { resolvePost = resolve; })
      : Promise.resolve(new Response(JSON.stringify(page), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectedCasesPage navigate={vi.fn()}/>);
    await screen.findByText("No persisted cases");
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));
    fireEvent.change(screen.getByLabelText("Case name"), { target: { value: "Retry me" } });
    const submit = screen.getByRole("button", { name: "Create case" });
    fireEvent.click(submit); fireEvent.click(submit);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
    resolvePost?.(new Response(JSON.stringify({ code: "database_unavailable", message: "The evidence database is unavailable.", retryable: true }), { status: 503, headers: { "Content-Type": "application/json" } }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The evidence database is unavailable.");
    expect(screen.getByLabelText("Case name")).toHaveValue("Retry me");
  });

  it("validates required trimmed fields before calling the API", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify(page), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectedCasesPage navigate={vi.fn()}/>);
    await screen.findByText("No persisted cases");
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));
    fireEvent.change(screen.getByLabelText("Case name"), { target: { value: "   " } });
    fireEvent.submit(screen.getByRole("form", { name: "Create case" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a case name");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
