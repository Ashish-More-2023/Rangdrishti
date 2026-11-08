"""Build candidates_report.json: what was considered, rejected, selected and validated."""
from __future__ import annotations

from collections import Counter


def distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    v = sorted(values)

    def pct(p):  # nearest-rank percentile, deterministic
        return v[min(len(v) - 1, max(0, round(p / 100 * (len(v) - 1))))]

    bins = Counter(min(9, int(x * 10)) for x in v)
    return {
        "count": len(v), "min": v[0], "p10": pct(10), "p25": pct(25), "median": pct(50),
        "p75": pct(75), "p90": pct(90), "max": v[-1], "mean": round(sum(v) / len(v), 4),
        "histogram": {f"{i / 10:.1f}-{(i + 1) / 10:.1f}": bins.get(i, 0) for i in range(10)},
    }


def feature_means(scored) -> dict:
    if not scored:
        return {}
    names = scored[0].features.keys()
    return {n: round(sum(s.features[n].value for s in scored) / len(scored), 4) for n in names}
