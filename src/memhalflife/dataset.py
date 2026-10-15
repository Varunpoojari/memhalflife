"""Dataset layout and record collection.

    <root>/dataset.json                         {"synthetic": bool, ...}
    <root>/custody.jsonl                        chain-of-custody log (real images)
    <root>/<scenario>/<rep>/t<minutes>/<plugin>.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .extract import score_image
from .models import Scenario

_T_RE = re.compile(r"^t(\d+(?:\.\d+)?)$")


def t_dirname(t: float) -> str:
    return f"t{int(t)}" if float(t).is_integer() else f"t{t}"


def slot_dir(root: str | Path, scenario: str, rep: str | int, t: float) -> Path:
    return Path(root) / scenario / str(rep) / t_dirname(t)


def read_manifest(root: str | Path) -> dict:
    p = Path(root) / "dataset.json"
    if p.is_file():
        return json.loads(p.read_text())
    return {}


def write_manifest(root: str | Path, **fields) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "dataset.json").write_text(json.dumps(fields, indent=2, sort_keys=True))


def collect_records(root: str | Path, scenarios: dict[str, Scenario]) -> list[dict]:
    """Score every image found in the dataset into per-artefact records."""
    records: list[dict] = []
    root = Path(root)
    for sid, sc in scenarios.items():
        sdir = root / sid
        if not sdir.is_dir():
            continue
        for rep_dir in sorted(p for p in sdir.iterdir() if p.is_dir()):
            for t_dir in sorted(p for p in rep_dir.iterdir() if p.is_dir()):
                m = _T_RE.match(t_dir.name)
                if not m:
                    continue
                t = float(m.group(1))
                for res in score_image(sc, t_dir):
                    records.append(
                        {
                            "scenario": sid,
                            "rep": rep_dir.name,
                            "t": t,
                            "artefact": res.artefact_id,
                            "category": res.category,
                            "weight": res.weight,
                            "status": res.status,
                        }
                    )
    return records
