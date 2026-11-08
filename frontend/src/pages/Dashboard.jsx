import { useCallback, useEffect, useState } from "react";
import ConnectionStatus from "../components/ConnectionStatus.jsx";
import ResultsPanel from "../components/ResultsPanel.jsx";
import { fetchHealth } from "../api/health.js";
import { connectionMode } from "../api/client.js";

export default function Dashboard() {
  const [state, setState] = useState("checking");
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  const check = useCallback(async () => {
    setState("checking");
    try {
      setHealth(await fetchHealth());
      setError(null);
      setState("connected");
    } catch (err) {
      setError(err);
      setState("failed");
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <div className="min-h-screen bg-paper text-ink dark:bg-night dark:text-moon">
      <main className="mx-auto max-w-6xl px-6 py-10 sm:py-14">
        <header className="flex flex-wrap items-baseline justify-between gap-4 border-b border-line pb-5 dark:border-night-line">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Rangdrishti</h1>
            <p className="text-muted dark:text-moon/70">Promo picks from microdrama screenplays, with exact timestamps.</p>
          </div>
          <ConnectionStatus state={state} health={health} error={error} mode={connectionMode()} onRetry={check} />
        </header>
        <div className="mt-10">{state === "connected" ? <ResultsPanel /> : null}</div>
      </main>
    </div>
  );
}
