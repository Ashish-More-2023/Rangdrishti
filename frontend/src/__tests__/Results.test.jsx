import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResultsPanel from "../components/ResultsPanel.jsx";
import { fetchClip, fetchResults, fetchShows } from "../api/results.js";

vi.mock("../api/results.js", () => ({
  fetchShows: vi.fn(),
  fetchResults: vi.fn(),
  fetchClip: vi.fn(),
  csvUrl: (slug) => `/api/shows/${slug}/promos.csv`,
}));

function promo(id, rank, episode, extra = {}) {
  return {
    id, rank, episode_id: episode, post_first_rank: null, start: "00:10.00", end: "00:40.00", start_s: 10, end_s: 40,
    duration_s: 30, final_score: 0.8 - rank / 100, rule_score: 0.7, ai_score: 0.8, judged: true, verdict: "post",
    hook: `Hook of ${id}`, cliffhanger: `Cliff of ${id}`, why: "Because.", scores: { hook: 8, cliffhanger: 7, standalone: 6 },
    trimmed: false, flags: [], ...extra,
  };
}

const RESULTS = {
  show: { slug: "synthetic-show", title: "Synthetic Show" },
  run: { provider: "mock", model: "mock-1", is_mock: true },
  counts: { candidates: 3 },
  failed_episodes: [],
  post_first: ["E001-W01000-04000"],
  episodes: ["E001", "E002"],
  csv_available: true,
  promos: [
    promo("E001-W01000-04000", 1, "E001", { post_first_rank: 1 }),
    promo("E002-W01000-04000", 2, "E002", { verdict: "maybe" }),
    promo("E002-W05000-08000", 3, "E002", { verdict: "skip" }),
  ],
};

describe("ResultsPanel", () => {
  beforeEach(() => {
    vi.mocked(fetchShows).mockResolvedValue([{ slug: "synthetic-show", title: "Synthetic Show", has_promos: true }]);
    vi.mocked(fetchResults).mockResolvedValue(RESULTS);
    vi.mocked(fetchClip).mockReset();
  });

  it("shows the post-first picks, the CSV link and the mock warning", async () => {
    render(<ResultsPanel />);
    expect(await screen.findByRole("heading", { name: "Synthetic Show" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Post-first pick 1: E001/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download CSV" })).toHaveAttribute("href", "/api/shows/synthetic-show/promos.csv");
    expect(screen.getByRole("note")).toHaveTextContent(/offline mock/);
  });

  it("filters the table by episode and verdict", async () => {
    render(<ResultsPanel />);
    await screen.findByRole("heading", { name: "Synthetic Show" });
    const rows = () => within(screen.getByRole("table")).getAllByRole("row").length - 1;
    expect(rows()).toBe(3);
    await userEvent.selectOptions(screen.getByLabelText("Episode"), "E002");
    expect(rows()).toBe(2);
    await userEvent.selectOptions(screen.getByLabelText("Verdict"), "skip");
    expect(rows()).toBe(1);
  });

  it("opens a promo with its script and closes it", async () => {
    vi.mocked(fetchClip).mockResolvedValue({
      promo: RESULTS.promos[1], original: null,
      lines: [{ id: "E002-S01-B001", kind: "dialogue", label: "ANA (Furious)", start: "00:10.30", text: '"Where were you?"', partial: false }],
    });
    render(<ResultsPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "E002-W01000-04000" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText('"Where were you?"')).toBeInTheDocument();
    expect(fetchClip).toHaveBeenCalledWith("synthetic-show", "E002-W01000-04000");
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("explains how to produce results when there are none", async () => {
    vi.mocked(fetchShows).mockResolvedValue([]);
    render(<ResultsPanel />);
    expect(await screen.findByText("No parsed shows yet.")).toBeInTheDocument();
    expect(screen.getByText(/judge_promos/)).toBeInTheDocument();
  });
});
