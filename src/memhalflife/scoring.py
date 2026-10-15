"""Detection Completeness Score (DCS) v2.

v1 (the simple Y/P/N average) is kept for comparability with earlier work.
v2 weights each artefact by forensic value so that losing one high-fidelity
artefact (e.g. the attacker's command line) costs more than losing context.
Artefacts whose plugin output is missing (status NA) are excluded, never
counted as absent.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import ArtefactResult


def dcs(results: Iterable[ArtefactResult], weighted: bool = True) -> float | None:
    num = den = 0.0
    for r in results:
        v = r.value
        if v is None:
            continue
        w = r.weight if weighted else 1.0
        num += w * v
        den += w
    return None if den == 0 else num / den


def dcs_by_category(results: Iterable[ArtefactResult], weighted: bool = True) -> dict[str, float]:
    groups: dict[str, list[ArtefactResult]] = defaultdict(list)
    for r in results:
        groups[r.category].append(r)
    out = {}
    for cat, rs in groups.items():
        s = dcs(rs, weighted)
        if s is not None:
            out[cat] = s
    return out


def coverage(results: Iterable[ArtefactResult]) -> float:
    """Fraction of artefacts that could be judged (non-NA)."""
    rs = list(results)
    return 0.0 if not rs else sum(r.status != "NA" for r in rs) / len(rs)
