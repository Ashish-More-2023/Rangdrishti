const TONE = {
  checking: { dot: "bg-muted animate-pulse", label: "Checking the backend…" },
  connected: { dot: "bg-ok", label: "Backend connected" },
  failed: { dot: "bg-bad", label: "Backend not reachable" },
};

export default function ConnectionStatus({ state, health, error, mode, onRetry }) {
  const tone = TONE[state];
  return (
    <section aria-live="polite" className="text-sm">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span aria-hidden="true" className={`inline-block size-2.5 rounded-full ${tone.dot}`} />
        <span className="font-medium">{tone.label}</span>
        {state === "connected" && health && (
          <span className="flex flex-wrap gap-x-2 text-muted dark:text-moon/60">
            <span>{`${health.service} v${health.version}`}</span>
            <span>database {health.database}</span>
            <span>{`${health.latencyMs} ms`}</span>
            <span>{mode}</span>
          </span>
        )}
        {state !== "checking" && (
          <button type="button" onClick={onRetry}
            className="rounded border border-ink/20 px-2 py-0.5 hover:border-reel hover:text-reel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-reel dark:border-moon/30">
            Check again
          </button>
        )}
      </p>
      {state === "failed" && error && (
        <p className="mt-1 text-bad">{error.message} <span className="text-muted">({error.code})</span></p>
      )}
    </section>
  );
}
