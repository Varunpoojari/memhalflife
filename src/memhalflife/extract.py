"""Evaluate scenario artefacts against Volatility 3 JSON plugin output.

Layout of an analysed image directory (written by `memhalflife analyse`):

    <image_dir>/<full.plugin.Name>.json     # `vol -r json` output

Rows are flattened (pstree-style ``__children``) before matching.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import ArtefactResult, ArtefactSpec, Scenario


def flatten_rows(rows: Any) -> list[dict]:
    out: list[dict] = []
    stack = list(rows) if isinstance(rows, list) else [rows]
    while stack:
        row = stack.pop(0)
        if not isinstance(row, dict):
            continue
        children = row.get("__children") or []
        out.append({k: v for k, v in row.items() if k != "__children"})
        stack = list(children) + stack
    return out


def load_plugin_rows(image_dir: str | Path, plugin: str) -> list[dict] | None:
    """Return rows for a plugin, or None if its output is absent/unreadable."""
    p = Path(image_dir) / f"{plugin}.json"
    if not p.is_file():
        return None
    try:
        return flatten_rows(json.loads(p.read_text(encoding="utf-8", errors="replace")))
    except json.JSONDecodeError:
        return None


def _row_matches(row: dict, conds: dict[str, str]) -> bool:
    for fld, rx in conds.items():
        if fld not in row or row[fld] is None:
            return False
        if re.search(rx, str(row[fld])) is None:
            return False
    return True


def evaluate_artefact(spec: ArtefactSpec, rows: list[dict] | None) -> str:
    """Return Y (full match), P (only partial match), N (absent) or NA (no data)."""
    if rows is None:
        return "NA"
    full = sum(1 for r in rows if _row_matches(r, spec.match))
    if full >= spec.min_rows:
        return "Y"
    if spec.partial and any(_row_matches(r, spec.partial) for r in rows):
        return "P"
    return "N"


def score_image(scenario: Scenario, image_dir: str | Path) -> list[ArtefactResult]:
    cache: dict[str, list[dict] | None] = {}
    results = []
    for spec in scenario.artefacts:
        if spec.plugin not in cache:
            cache[spec.plugin] = load_plugin_rows(image_dir, spec.plugin)
        status = evaluate_artefact(spec, cache[spec.plugin])
        results.append(ArtefactResult(spec.id, spec.category, spec.weight, status))
    return results
