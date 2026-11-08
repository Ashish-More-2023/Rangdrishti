import { useCallback, useEffect, useMemo, useState } from "react";
import { csvUrl, fetchClip, fetchResults, fetchShows } from "../api/results.js";
import PostFirst from "./PostFirst.jsx";
import PromoDetail from "./PromoDetail.jsx";
import PromoTable from "./PromoTable.jsx";

const PIPELINE = [
  'python manage.py parse_show ..\\data\\input',
  'python manage.py find_candidates "..\\data\\processed\\<show-slug>"',
  'python manage.py judge_promos "..\\data\\processed\\<show-slug>"',
];

function NextSteps({ message }) {
  return (
    <section className="rounded-lg border border-line p-5 dark:border-night-line">
      <p className="font-medium">{message}</p>
      <p className="mt-2 text-muted dark:text-moon/70">Run the pipeline from the backend folder, then reload this page:</p>
      <pre className="mt-3 overflow-x-auto text-sm">{PIPELINE.join("\n")}</pre>
    </section>
  );
}

export default function ResultsPanel() {
  const [state, setState] = useState({ status: "loading" });
  const [filters, setFilters] = useState({ episode: "all", verdict: "all" });
  const [open, setOpen] = useState(null); // { id, detail, loading, error }

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const shows = await fetchShows();
      const show = shows.find((s) => s.has_promos) || shows[0];
      if (!show) return setState({ status: "empty", message: "No parsed shows yet." });
      if (!show.has_promos) return setState({ status: "empty", message: `${show.title} has no ranked promos yet.` });
      setState({ status: "ready", results: await fetchResults(show.slug) });
    } catch (error) {
      setState({ status: "error", error });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const results = state.results;
  const visible = useMemo(() => (results?.promos || []).filter((p) =>
    (filters.episode === "all" || p.episode_id === filters.episode) && (filters.verdict === "all" || p.verdict === filters.verdict),
  ), [results, filters]);
  const postFirst = useMemo(() => (results?.post_first || []).map((id) => results.promos.find((p) => p.id === id)).filter(Boolean), [results]);

  const openPromo = useCallback(async (id) => {
    setOpen({ id, loading: true });
    try {
      const detail = await fetchClip(results.show.slug, id);
      setOpen({ id, detail, loading: false });
    } catch (error) {
      setOpen({ id, error, loading: false });
    }
  }, [results]);

  if (state.status === "loading") return <p className="text-muted">Loading results…</p>;
  if (state.status === "empty") return <NextSteps message={state.message} />;
  if (state.status === "error") {
    return (
      <p className="text-bad">
        {state.error.message}{" "}
        <button type="button" onClick={load} className="underline">Try again</button>
      </p>
    );
  }

  const { show, run, counts, failed_episodes: failed } = results;
  return (
    <div className="space-y-12">
      <header>
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{show.title}</h2>
        <p className="mt-2 text-muted dark:text-moon/70">
          {counts.candidates} promos from {results.episodes.length} episodes, judged by {run.model}.{" "}
          {results.csv_available && <a href={csvUrl(show.slug)} download className="font-medium text-reel underline-offset-2 hover:underline">Download CSV</a>}
        </p>
        {run.is_mock && (
          <p role="note" className="mt-4 rounded-lg bg-amber/10 p-3 text-amber">
            These verdicts come from the offline mock, not a model, so they are placeholders. Set LLM_PROVIDER=gemini in .env and run judge_promos for real judgements.
          </p>
        )}
        {failed?.length > 0 && (
          <p className="mt-4 rounded-lg bg-bad/10 p-3 text-bad">
            The model failed on {failed.join(", ")}; those use rule scores only. Run judge_promos again to retry them.
          </p>
        )}
      </header>
      <PostFirst promos={postFirst} onOpen={openPromo} />
      <PromoTable promos={visible} episodes={results.episodes} filters={filters} onFilter={setFilters} onOpen={openPromo} />
      {open && <PromoDetail detail={open.detail} loading={open.loading} error={open.error} onClose={() => setOpen(null)} />}
    </div>
  );
}
