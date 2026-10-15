"""Acquisition-SLA model: turn decay curves + acquisition latency into IR guidance.

Question answered: *given how long it takes my team/cloud tooling to get a
memory image after detection, how much evidence do I expect to recover per
technique?*  Latency is modelled as lognormal from a median and a p95, so
profiles stay easy to measure and easy to explain.

IMPORTANT: shipped latency profiles are illustrative placeholders
(`assumed = true`). Replace them with latencies you have measured in your own
environment (see docs/CLOUD_ACQUISITION.md).
"""

from __future__ import annotations

import math
import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .survival import Curve, value_at

_Z95 = 1.6448536269514722


@dataclass(frozen=True)
class LatencyProfile:
    id: str
    description: str
    median_min: float
    p95_min: float
    assumed: bool = True

    @property
    def mu(self) -> float:
        return math.log(self.median_min)

    @property
    def sigma(self) -> float:
        if self.p95_min <= self.median_min:
            return 1e-6
        return math.log(self.p95_min / self.median_min) / _Z95


def load_profiles(path: str | Path) -> dict[str, LatencyProfile]:
    with Path(path).open("rb") as fh:
        raw = tomllib.load(fh)
    out = {}
    for pid, p in raw.get("profile", {}).items():
        out[pid] = LatencyProfile(
            id=pid,
            description=p.get("description", ""),
            median_min=float(p["median_min"]),
            p95_min=float(p["p95_min"]),
            assumed=bool(p.get("assumed", True)),
        )
    return out


@dataclass(frozen=True)
class SlaResult:
    scenario: str
    profile: str
    expected_retention: float  # E[DCS(latency)] / DCS(0)
    p_retain_ge_threshold: float  # P(DCS(latency)/DCS(0) >= threshold)
    threshold: float
    extrapolated_share: float  # share of draws beyond the observed window


def simulate(
    curve: Curve,
    profile: LatencyProfile,
    threshold: float = 0.8,
    draws: int = 20000,
    seed: int = 7,
) -> SlaResult:
    y0 = curve.mean[0]
    if y0 <= 0:
        return SlaResult(curve.scenario, profile.id, math.nan, math.nan, threshold, 0.0)
    rng = random.Random(seed)
    tot = hits = beyond = 0
    for _ in range(draws):
        lat = rng.lognormvariate(profile.mu, profile.sigma)
        rel = value_at(curve.ts, curve.mean, lat) / y0
        tot += rel
        hits += rel >= threshold
        beyond += lat > curve.ts[-1]
    return SlaResult(curve.scenario, profile.id, tot / draws, hits / draws, threshold, beyond / draws)
