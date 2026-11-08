import { useEffect, useRef } from "react";
import Verdict from "./Verdict.jsx";

function Score({ label, value, outOf = 10 }) {
  if (value === null || value === undefined) return null;
  return (
    <div>
      <dt className="text-sm text-muted dark:text-moon/60">{label}</dt>
      <dd className="font-semibold tabular-nums">{outOf === 1 ? value.toFixed(2) : `${value}/10`}</dd>
    </div>
  );
}

export default function PromoDetail({ detail, loading, error, onClose }) {
  const closeRef = useRef(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const p = detail?.promo;
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-ink/40" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label="Promo details" onClick={(e) => e.stopPropagation()}
        className="h-full w-full max-w-xl overflow-y-auto bg-paper p-6 shadow-2xl dark:bg-night">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-xl font-semibold">{p ? `${p.id}` : "Promo"}</h2>
          <button ref={closeRef} type="button" onClick={onClose}
            className="rounded border border-ink/20 px-2 py-0.5 text-sm hover:border-reel hover:text-reel focus-visible:outline-2 focus-visible:outline-reel dark:border-moon/30">
            Close
          </button>
        </div>
        {loading && <p className="mt-6 text-muted">Loading the script…</p>}
        {error && <p className="mt-6 text-bad">{error.message}</p>}
        {p && (
          <>
            <p className="mt-2 tabular-nums">
              {p.episode_id}, {p.start}–{p.end} ({p.duration_s.toFixed(1)} s) <Verdict value={p.verdict} />
            </p>
            {detail.original && <p className="mt-1 text-sm text-muted">Trimmed by the AI from {detail.original.start}–{detail.original.end}; checked against the cut rules.</p>}
            <dl className="mt-5 space-y-3">
              <div><dt className="text-sm text-muted dark:text-moon/60">Hook</dt><dd>{p.hook || "–"}</dd></div>
              <div><dt className="text-sm text-muted dark:text-moon/60">Cliffhanger</dt><dd>{p.cliffhanger || "–"}</dd></div>
              <div><dt className="text-sm text-muted dark:text-moon/60">Why it works</dt><dd>{p.why || "–"}</dd></div>
            </dl>
            <dl className="mt-5 grid grid-cols-3 gap-4 sm:grid-cols-6">
              <Score label="Final" value={p.final_score} outOf={1} />
              <Score label="Rules" value={p.rule_score} outOf={1} />
              <Score label="AI" value={p.ai_score} outOf={1} />
              <Score label="Hook" value={p.scores?.hook} />
              <Score label="Cliff" value={p.scores?.cliffhanger} />
              <Score label="Alone" value={p.scores?.standalone} />
            </dl>
            <h3 className="mt-7 font-semibold">Script inside the clip</h3>
            <ol className="mt-3 space-y-2 text-sm">
              {detail.lines.map((l) => (
                <li key={l.id} className={l.kind === "dialogue" ? "" : "text-muted dark:text-moon/60"}>
                  <span className="tabular-nums text-muted">{l.start}</span>{" "}
                  <span className={l.kind === "dialogue" ? "font-semibold" : ""}>{l.label}:</span> {l.text}
                  {l.partial && <span className="text-muted"> (partly outside the clip)</span>}
                </li>
              ))}
            </ol>
          </>
        )}
      </aside>
    </div>
  );
}
