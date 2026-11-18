"""GTA VI launch-day Twitch viewer forecaster.

An hour-1 viewer count anchors the forecast. Each comparable supplies a curve
of log(viewers / hour-1 viewers) for hours 1..24; comparables are weighted by
how close their day_start is to the case's day_start. Weighted moments of those
log-ratios give a mean and spread at every forecast hour, which are blended
with a generic launch-decay prior and turned into five quantiles.

Standard library only.
"""

import datetime
import json
import math
import os
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
Z = (-1.645, -0.674, 0.0, 0.674, 1.645)
MIN_VIEWERS = 0.01
MAX_VIEWERS = 1e9


def parse_day(value):
    """Parse an ISO-8601 day_start into an aware datetime."""
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def anchor_viewers(case):
    """Extract the hour-1 viewer count from a case's `known` field."""
    known = case.get("known")
    if isinstance(known, (int, float)):
        return float(known)
    if isinstance(known, dict):
        if "viewers" in known:
            return float(known["viewers"])
        for key in ("1", 1):
            if key in known:
                return float(known[key])
    if isinstance(known, list):
        for item in known:
            if isinstance(item, dict) and item.get("hour", item.get("h")) in (1, "1"):
                return float(item["viewers"])
    raise ValueError("case has no hour-1 viewer count in 'known'")


def comparable_rows(comp):
    """Return the hourly rows of a comparable regardless of the list key."""
    for key in ("hourly", "hours", "rows", "data"):
        if isinstance(comp.get(key), list):
            return comp[key]
    return []


def comparable_curve(comp):
    """Return {hour: log(viewers/anchor)} for hours 1..24, or None."""
    day_start = comp.get("day_start")
    if not day_start:
        return None
    day = parse_day(day_start)
    viewers = {}
    for row in comparable_rows(comp):
        source = row.get("from")
        if not source or not row.get("viewers"):
            continue
        try:
            when = datetime.datetime.fromisoformat(source.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        hour = int((when - day).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            viewers[hour] = float(row["viewers"])
    if 1 not in viewers or viewers[1] <= 0:
        return None
    anchor = viewers[1]
    return {
        hour: math.log(value / anchor)
        for hour, value in viewers.items()
        if value > 0
    }


def comparable_weight(case_day, comp):
    """Weight by exponential decay in the distance between day_start values."""
    if not comp.get("day_start"):
        return 0.0
    distance = abs((case_day - parse_day(comp["day_start"])).total_seconds()) / 86400.0
    return math.exp(-distance / 400.0)


def forecast_hours(case):
    """Return the sorted forecast hours restricted to 2..24."""
    hours = []
    for row in case.get("forecast", []):
        hour = row.get("hour", row.get("h")) if isinstance(row, dict) else row
        hour = int(hour)
        if 2 <= hour <= 24:
            hours.append(hour)
    return sorted(hours)


def forecast_case(case):
    p1 = anchor_viewers(case)
    case_day = parse_day(case["day_start"])

    samples = {}
    for comp in case.get("comparables", []) or []:
        curve = comparable_curve(comp)
        if not curve:
            continue
        weight = comparable_weight(case_day, comp)
        if weight <= 0:
            continue
        for hour, log_ratio in curve.items():
            if hour >= 2:
                samples.setdefault(hour, []).append((log_ratio, weight))

    out = []
    for hour in forecast_hours(case):
        points = samples.get(hour, [])
        if points:
            total = sum(weight for _, weight in points)
            mean = sum(value * weight for value, weight in points) / total
            var = sum(weight * (value - mean) ** 2 for value, weight in points) / total
        else:
            mean = 0.0
            var = 0.0
        sd = min(0.9, max(0.05, math.sqrt(var)))
        blended = 0.65 * mean + 0.35 * (-0.18 * math.log(hour))
        quantiles = [
            round(min(MAX_VIEWERS, max(MIN_VIEWERS, p1 * math.exp(blended + z * sd))), 2)
            for z in Z
        ]
        quantiles.sort()
        out.append({"hour": hour, "q": quantiles})
    return {"hours": out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        target = OUTPUT_DIR / f"{path.stem}.out"
        target.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
