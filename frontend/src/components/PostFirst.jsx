// The ten promos to post first, shown in the shape they will be watched in: vertical 9:16 frames.
export default function PostFirst({ promos, onOpen }) {
  if (!promos.length) return null;
  return (
    <section aria-labelledby="post-first-heading">
      <h2 id="post-first-heading" className="text-xl font-semibold">Post these first</h2>
      <p className="mt-1 text-muted dark:text-moon/70">Best-ranked promos, at most one per episode. Open one to read its script.</p>
      <ol className="mt-5 flex snap-x gap-4 overflow-x-auto pb-3">
        {promos.map((p) => (
          <li key={p.id} className="snap-start">
            <button type="button" onClick={() => onOpen(p.id)}
              aria-label={`Post-first pick ${p.post_first_rank}: ${p.episode_id} ${p.start} to ${p.end}`}
              className="flex aspect-[9/16] w-44 flex-col justify-between rounded-2xl bg-tile p-4 text-left text-white shadow-lg ring-reel transition hover:ring-2 focus-visible:outline-none focus-visible:ring-4 sm:w-52">
              <span className="flex items-baseline justify-between text-sm text-white/70">
                <span className="text-2xl font-bold text-white">{p.post_first_rank}</span>
                <span>{p.episode_id}</span>
              </span>
              <span className="text-[0.95rem] leading-snug font-medium">{p.hook}</span>
              <span className="text-sm text-white/75">
                <span className="block border-t border-white/20 pt-2 italic">{p.cliffhanger}</span>
                <span className="mt-2 block tabular-nums text-white/60">{p.start}–{p.end}, {p.duration_s.toFixed(0)} s</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
