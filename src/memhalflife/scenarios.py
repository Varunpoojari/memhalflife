"""Load and validate declarative scenario definitions (TOML)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .models import ArtefactSpec, Scenario


class ScenarioError(ValueError):
    pass


def _compile_check(sid: str, aid: str, conds: dict[str, str]) -> None:
    for fld, rx in conds.items():
        try:
            re.compile(rx)
        except re.error as exc:  # pragma: no cover - message path
            raise ScenarioError(f"{sid}/{aid}: bad regex for field {fld!r}: {exc}") from exc


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    try:
        sid = raw["id"]
        timepoints = tuple(float(t) for t in raw["timepoints"])
    except KeyError as exc:
        raise ScenarioError(f"{path.name}: missing required key {exc}") from exc

    if len(timepoints) < 2 or list(timepoints) != sorted(set(timepoints)):
        raise ScenarioError(f"{sid}: timepoints must be ≥2 unique, ascending values")

    artefacts = []
    seen: set[str] = set()
    for a in raw.get("artefact", []):
        aid = a["id"]
        if aid in seen:
            raise ScenarioError(f"{sid}: duplicate artefact id {aid}")
        seen.add(aid)
        weight = float(a.get("weight", 1))
        if weight <= 0:
            raise ScenarioError(f"{sid}/{aid}: weight must be > 0")
        match = dict(a.get("match", {}))
        partial = dict(a.get("partial", {}))
        if not match:
            raise ScenarioError(f"{sid}/{aid}: 'match' conditions are required")
        _compile_check(sid, aid, match)
        _compile_check(sid, aid, partial)
        artefacts.append(
            ArtefactSpec(
                id=aid,
                category=a.get("category", "execution"),
                weight=weight,
                plugin=a["plugin"],
                match=match,
                partial=partial,
                description=a.get("description", ""),
                min_rows=int(a.get("min_rows", 1)),
                synthetic=dict(a.get("synthetic", {})),
            )
        )
    if not artefacts:
        raise ScenarioError(f"{sid}: no artefacts defined")

    return Scenario(
        id=sid,
        name=raw.get("name", sid),
        technique=raw.get("technique", ""),
        tactic=raw.get("tactic", ""),
        platform=raw.get("platform", "windows"),
        environment=raw.get("environment", "onprem"),
        timepoints=timepoints,
        artefacts=tuple(artefacts),
        reboot_at=float(raw["reboot_at"]) if "reboot_at" in raw else None,
        notes=raw.get("notes", ""),
    )


def load_all(directory: str | Path) -> dict[str, Scenario]:
    out: dict[str, Scenario] = {}
    for p in sorted(Path(directory).glob("*.toml")):
        sc = load_scenario(p)
        if sc.id in out:
            raise ScenarioError(f"duplicate scenario id {sc.id}")
        out[sc.id] = sc
    return out
