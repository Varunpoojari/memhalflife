"""Evidence decay analysis: curves, half-lives, bootstrap CIs, pattern classes.

Input is a list of *records*, one per (scenario, replicate, timepoint, artefact):

    {"scenario","rep","t","artefact","category","weight","status"}

Replicates are whole attack runs imaged at every timepoint, so the bootstrap
resamples *runs* (all timepoints together), preserving within-run correlation.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

from .models import STATUS_VALUE

Record = dict


def _score(rows: list[Record], weighted: bool) -> float | None:
    num = den = 0.0
    for r in rows:
        v = STATUS_VALUE.get(r["status"])
        if v is None:
            continue
        w = float(r["weight"]) if weighted else 1.0
        num += w * v
        den += w
    return None if den == 0 else num / den


def run_scores(records: list[Record], scenario: str, weighted: bool = True) -> dict[str, dict[float, float]]:
    """rep -> {t -> DCS}"""
    grouped: dict[tuple[str, float], list[Record]] = defaultdict(list)
    for r in records:
        if r["scenario"] == scenario:
            grouped[(str(r["rep"]), float(r["t"]))].append(r)
    out: dict[str, dict[float, float]] = defaultdict(dict)
    for (rep, t), rows in grouped.items():
        s = _score(rows, weighted)
        if s is not None:
            out[rep][t] = s
    return out


def mean_curve(runs: dict[str, dict[float, float]]) -> tuple[list[float], list[float]]:
    by_t: dict[float, list[float]] = defaultdict(list)
    for series in runs.values():
        for t, v in series.items():
            by_t[t].append(v)
    ts = sorted(by_t)
    return ts, [sum(by_t[t]) / len(by_t[t]) for t in ts]


@dataclass(frozen=True)
class HalfLife:
    value: float | None  # minutes; None if undefined
    censored: bool  # True => never fell to the threshold inside the observed window
    lower_bound: float  # if censored: the last observed timepoint


def time_to_fraction(ts: list[float], ys: list[float], fraction: float = 0.5) -> HalfLife:
    """First time the curve falls to `fraction` of its initial value (linear interpolation)."""
    if not ts or ys[0] <= 0:
        return HalfLife(None, False, ts[-1] if ts else 0.0)
    thr = fraction * ys[0]
    for i in range(len(ts)):
        if ys[i] <= thr:
            if i == 0:
                return HalfLife(ts[0], False, ts[0])
            t0, t1, y0, y1 = ts[i - 1], ts[i], ys[i - 1], ys[i]
            frac = 0.0 if y0 == y1 else (y0 - thr) / (y0 - y1)
            return HalfLife(t0 + frac * (t1 - t0), False, t1)
    return HalfLife(None, True, ts[-1])


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return math.nan
    k = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi or sorted_vals[lo] == sorted_vals[hi]:
        return sorted_vals[lo]
    if math.isinf(sorted_vals[hi]):
        # censored (never reached threshold) resamples are +inf; avoid inf-inf = nan
        return math.inf if (k - lo) > 0 else sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


@dataclass(frozen=True)
class Curve:
    scenario: str
    ts: list[float]
    mean: list[float]
    lo: list[float]
    hi: list[float]
    n_runs: int


def curve_with_ci(
    records: list[Record],
    scenario: str,
    weighted: bool = True,
    boots: int = 2000,
    alpha: float = 0.05,
    seed: int = 1337,
) -> Curve:
    runs = run_scores(records, scenario, weighted)
    ts, means = mean_curve(runs)
    reps = list(runs)
    rng = random.Random(seed)
    samples: dict[float, list[float]] = {t: [] for t in ts}
    if len(reps) >= 2:
        for _ in range(boots):
            pick = [reps[rng.randrange(len(reps))] for _ in reps]
            for t in ts:
                vals = [runs[r][t] for r in pick if t in runs[r]]
                if vals:
                    samples[t].append(sum(vals) / len(vals))
    lo, hi = [], []
    for t, m in zip(ts, means):
        s = sorted(samples[t])
        lo.append(_percentile(s, alpha / 2) if s else m)
        hi.append(_percentile(s, 1 - alpha / 2) if s else m)
    return Curve(scenario, ts, means, lo, hi, len(reps))


@dataclass(frozen=True)
class HalfLifeCI:
    point: HalfLife
    lo: float | None
    hi: float | None  # math.inf => upper bound beyond the observed window
    pct_censored: float


def halflife_with_ci(
    records: list[Record],
    scenario: str,
    fraction: float = 0.5,
    weighted: bool = True,
    boots: int = 2000,
    alpha: float = 0.05,
    seed: int = 1337,
) -> HalfLifeCI:
    runs = run_scores(records, scenario, weighted)
    ts, means = mean_curve(runs)
    point = time_to_fraction(ts, means, fraction)
    reps = list(runs)
    if len(reps) < 2:
        return HalfLifeCI(point, None, None, 0.0)
    rng = random.Random(seed)
    vals: list[float] = []
    censored = 0
    for _ in range(boots):
        pick = [reps[rng.randrange(len(reps))] for _ in reps]
        bts, bys = [], []
        for t in ts:
            xs = [runs[r][t] for r in pick if t in runs[r]]
            if xs:
                bts.append(t)
                bys.append(sum(xs) / len(xs))
        hl = time_to_fraction(bts, bys, fraction)
        if hl.value is None and hl.censored:
            censored += 1
            vals.append(math.inf)
        elif hl.value is not None:
            vals.append(hl.value)
    vals.sort()
    if not vals:
        return HalfLifeCI(point, None, None, 0.0)
    return HalfLifeCI(
        point,
        _percentile(vals, alpha / 2),
        _percentile(vals, 1 - alpha / 2),
        censored / len(vals),
    )


def artefact_survival(records: list[Record], scenario: str) -> dict[str, tuple[list[float], list[float]]]:
    """Per-artefact survival S(t) = mean presence value across runs (Y=1, P=.5, N=0)."""
    acc: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r["scenario"] != scenario:
            continue
        v = STATUS_VALUE.get(r["status"])
        if v is not None:
            acc[r["artefact"]][float(r["t"])].append(v)
    out = {}
    for aid, by_t in acc.items():
        ts = sorted(by_t)
        out[aid] = (ts, [sum(by_t[t]) / len(by_t[t]) for t in ts])
    return out


def classify_pattern(ts: list[float], ys: list[float], reboot_at: float | None = None) -> str:
    """Stable | Cliff-edge | Gradual | Reboot-stable | Low-footprint | Undefined."""
    if not ts or ys[0] <= 0:
        return "Undefined"
    y0, yl = ys[0], ys[-1]
    if reboot_at is not None:
        pre = [y for t, y in zip(ts, ys) if t < reboot_at]
        post = [y for t, y in zip(ts, ys) if t >= reboot_at]
        if pre and post and post[0] >= 0.8 * pre[-1] and post[0] > 0:
            return "Reboot-stable"
    drops = [ys[i - 1] - ys[i] for i in range(1, len(ys))]
    if yl >= 0.8 * y0:
        return "Stable"
    if drops and max(drops) >= 0.6 * y0 and yl <= 0.15 * y0:
        return "Cliff-edge"
    if y0 < 0.3 and yl >= 0.5 * y0:
        return "Low-footprint"
    return "Gradual"


def value_at(ts: list[float], ys: list[float], t: float) -> float:
    """Piecewise-linear interpolation, clamped to the observed window."""
    if t <= ts[0]:
        return ys[0]
    if t >= ts[-1]:
        return ys[-1]
    for i in range(1, len(ts)):
        if t <= ts[i]:
            f = (t - ts[i - 1]) / (ts[i] - ts[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]
