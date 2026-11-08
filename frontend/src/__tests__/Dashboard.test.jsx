import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "../pages/Dashboard.jsx";
import { fetchHealth } from "../api/health.js";

vi.mock("../api/health.js", () => ({ fetchHealth: vi.fn() }));
vi.mock("../api/results.js", () => ({
  fetchShows: vi.fn().mockResolvedValue([]),
  fetchResults: vi.fn(),
  fetchClip: vi.fn(),
  csvUrl: vi.fn(),
}));

const HEALTHY = { service: "rangdrishti-api", version: "0.1.0", database: "ok", latencyMs: 12 };

describe("Dashboard", () => {
  beforeEach(() => vi.mocked(fetchHealth).mockReset());

  it("shows the connected state and backend details", async () => {
    vi.mocked(fetchHealth).mockResolvedValue(HEALTHY);
    render(<Dashboard />);

    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
    expect(screen.getByText("rangdrishti-api v0.1.0")).toBeInTheDocument();
    expect(screen.getByText("12 ms")).toBeInTheDocument();
    expect(await screen.findByText("No parsed shows yet.")).toBeInTheDocument();
  });

  it("shows the error and recovers when checked again", async () => {
    vi.mocked(fetchHealth)
      .mockRejectedValueOnce({ code: "network_error", message: "Can't reach the backend." })
      .mockResolvedValueOnce(HEALTHY);
    render(<Dashboard />);

    expect(await screen.findByText("Backend not reachable")).toBeInTheDocument();
    expect(screen.getByText(/Can't reach the backend/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Check again" }));

    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
    expect(fetchHealth).toHaveBeenCalledTimes(2);
  });
});
