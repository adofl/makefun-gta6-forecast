"""GTA VI launch-day Twitch viewer forecaster.

Idea: a launch's hour-1 count anchors a shape. Comparable past launches give
many hour-1-relative curves; weight the ones whose hour-1 and pre-launch
behaviour look most like the case, then produce quantiles from the weighted
distribution of log-ratios at each hour. Uses only the standard library.
"""
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]


def hourly_map(rows):
    """Map hour index (1-based from release-day 00:00Z) -> viewers."""
    out = {}
    for r in rows:
        f = r.get("from")
        if not f:
            continue
        # hour index from the row's own 'from' time relative to release day
        try:
            import datetime
            day = datetime.datetime.fromisoformat(r.get("_day_start", "").replace("Z", "+00:00")) if r.get("_day_start") else None
            t = datetime.datetime.fromisoformat(f.replace("Z", "+00:00"))
        except Exception:
            continue
        if day is not None:
            h = int((t - day).total_seconds() // 3600) + 1
            if 1 <= h <= 24:
                out[h] = max(1.0, float(r.get("viewers") or 0))
    return out


def comparable_curve(comp):
    """Return (anchor viewers at hour1, list of 24 log-ratios) or None."""
    day_start = comp.get("day_start")
    if not day_start:
        return None
    try:
        import datetime
        day = datetime.datetime.fromisoformat(day_start.replace("Z", "+00:00"))
    except Exception:
        return None
    vals = {}
    for r in comp.get("hourly") or []:
        f = r.get("from")
        if not f:
            continue
        try:
            t = datetime.datetime.fromisoformat(f.replace("Z", "+00:00"))
        except Exception:
            continue
        h = int((t - day).total_seconds() // 3600) + 1
        if 1 <= h <= 24 and r.get("viewers"):
            vals[h] = max(1.0, float(r["viewers"]))
    if 1 not in vals:
        return None
    a = vals[1]
    curve = {}
    for h in range(1, 25):
        if h in vals:
            curve[h] = math.log(vals[h] / a)
    return a, curve


def wdistance(case, comp):
    """Rough similarity between the case's pre-launch history and a comparable."""
    try:
        import datetime
        cd = datetime.datetime.fromisoformat(case["day_start"].replace("Z", "+00:00"))
        pd = datetime.datetime.fromisoformat(comp["day_start"].replace("Z", "+00:00"))
    except Exception:
        return 1.0
    d = abs((cd - pd).days)
    # prefer temporally near comparables, and those spanning the same unlock style
    w = math.exp(-d / 400.0)
    return max(w, 1e-9)


def forecast_case(case, name):
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name}: no hour-1 print")
    p1 = max(1.0, float(first.get("viewers") or 1))

    samples = {}  # hour -> list of log-ratio samples
    weights = {}
    for comp in case.get("comparables") or []:
        got = comparable_curve(comp)
        if not got:
            continue
        _, curve = got
        w = wdistance(case, comp)
        for h, lr in curve.items():
            if h < 2:
                continue
            samples.setdefault(h, []).append((lr, w))

    out = []
    for row in case.get("forecast", []):
        h = row["hour"]
        pts = samples.get(h, [])
        if pts:
            total = sum(w for _, w in pts)
            mean = sum(lr * w for lr, w in pts) / total
            var = sum(w * (lr - mean) ** 2 for lr, w in pts) / total
            sd = min(0.9, max(0.05, math.sqrt(var)))
        else:
            mean, sd = 0.0, 0.15 * math.sqrt(h - 1)
        # pulls toward a generic launch decay after the first hours
        generic = -0.18 * math.log(h)
        mean = 0.65 * mean + 0.35 * generic
        q = []
        for z in Z:
            v = p1 * math.exp(mean + z * sd)
            q.append(round(min(1e9, max(0.01, v)), 2))
        for i in range(1, len(q)):
            q[i] = max(q[i], q[i-1])
        out.append({"hour": h, "q": q})
    return {"hours": out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
