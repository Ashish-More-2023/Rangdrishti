const STYLE = {
  post: "bg-ok/10 text-ok",
  maybe: "bg-amber/10 text-amber",
  skip: "bg-bad/10 text-bad",
};

export default function Verdict({ value }) {
  if (!value) return <span className="text-muted">not judged</span>;
  return <span className={`rounded px-1.5 py-0.5 text-sm font-medium ${STYLE[value] || ""}`}>{value}</span>;
}
