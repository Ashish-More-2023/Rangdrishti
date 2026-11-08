import Verdict from "./Verdict.jsx";

function score(v) {
  return v === null || v === undefined ? "–" : v.toFixed(2);
}

export default function PromoTable({ promos, episodes, filters, onFilter, onOpen }) {
  return (
    <section aria-labelledby="all-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="all-heading" className="text-xl font-semibold">All promos <span className="font-normal text-muted">({promos.length})</span></h2>
        <div className="flex flex-wrap gap-3 text-sm">
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-episode">Episode</label>
            <select id="filter-episode" value={filters.episode} onChange={(e) => onFilter({ ...filters, episode: e.target.value })}
              className="rounded border border-line bg-transparent px-2 py-1 dark:border-night-line">
              <option value="all">All episodes</option>
              {episodes.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-verdict">Verdict</label>
            <select id="filter-verdict" value={filters.verdict} onChange={(e) => onFilter({ ...filters, verdict: e.target.value })}
              className="rounded border border-line bg-transparent px-2 py-1 dark:border-night-line">
              <option value="all">Any verdict</option>
              <option value="post">post</option>
              <option value="maybe">maybe</option>
              <option value="skip">skip</option>
            </select>
          </div>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line text-muted dark:border-night-line dark:text-moon/60">
            <tr>
              <th className="py-2 pr-3 font-medium">Rank</th>
              <th className="py-2 pr-3 font-medium">Clip</th>
              <th className="py-2 pr-3 font-medium">Time</th>
              <th className="py-2 pr-3 font-medium">Verdict</th>
              <th className="py-2 pr-3 font-medium">Score</th>
              <th className="py-2 font-medium">Hook</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line dark:divide-night-line">
            {promos.map((p) => (
              <tr key={p.id} className="align-top">
                <td className="py-2 pr-3 tabular-nums">{p.rank}</td>
                <td className="py-2 pr-3">
                  <button type="button" onClick={() => onOpen(p.id)} className="font-medium text-reel underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-reel">
                    {p.id}
                  </button>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap tabular-nums">{p.start}–{p.end} <span className="text-muted">({p.duration_s.toFixed(0)} s)</span></td>
                <td className="py-2 pr-3"><Verdict value={p.verdict} /></td>
                <td className="py-2 pr-3 tabular-nums">{score(p.final_score ?? p.rule_score)}</td>
                <td className="py-2 max-w-md">{p.hook || <span className="text-muted">–</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!promos.length && <p className="py-6 text-muted">No promos match these filters.</p>}
      </div>
    </section>
  );
}
