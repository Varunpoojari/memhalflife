"""Synthetic dataset generator for developing and testing the pipeline.

Writes fake Volatility-3-shaped JSON from each scenario's ``[artefact.synthetic]``
block. It exists so the whole pipeline (extraction -> scoring -> half-life ->
SLA -> report) can be exercised without 4 GB memory images.

SYNTHETIC OUTPUT IS NOT RESEARCH DATA. The dataset manifest is flagged
``synthetic: true`` and every report built from it carries a banner saying so.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .dataset import slot_dir, write_manifest
from .models import Scenario


def _noise_row(template: dict, i: int) -> dict:
    return {k: (f"benign-{i}" if isinstance(v, str) else v) for k, v in template.items()}


def generate(
    root: str | Path,
    scenarios: dict[str, Scenario],
    reps: int = 10,
    seed: int = 1,
) -> int:
    rng = random.Random(seed)
    root = Path(root)
    n_images = 0
    for sid, sc in scenarios.items():
        for rep in range(1, reps + 1):
            # one latent draw per (run, artefact): presence at t_i iff u <= p_i.
            # Gives within-run monotone loss (when p is non-increasing) while
            # keeping each timepoint's marginal presence probability = p_i.
            latent = {a.id: rng.random() for a in sc.artefacts}
            partial_coin = {a.id: rng.random() for a in sc.artefacts}
            for ti, t in enumerate(sc.timepoints):
                by_plugin: dict[str, list[dict]] = {}
                for a in sc.artefacts:
                    syn = a.synthetic
                    template = syn.get("row")
                    if not template:
                        continue
                    rows = by_plugin.setdefault(a.plugin, [])
                    if not rows:
                        rows.extend(_noise_row(template, i) for i in range(3))
                    p = syn.get("p", [1.0] * len(sc.timepoints))[ti]
                    if latent[a.id] <= p:
                        rows.append(dict(template))
                    elif syn.get("partial_row") and partial_coin[a.id] < 0.5:
                        rows.append(dict(syn["partial_row"]))
                out = slot_dir(root, sid, rep, t)
                out.mkdir(parents=True, exist_ok=True)
                for plugin, rows in by_plugin.items():
                    rng.shuffle(rows)
                    (out / f"{plugin}.json").write_text(json.dumps(rows))
                n_images += 1
    write_manifest(root, synthetic=True, generator="memhalflife.synthetic", seed=seed, reps=reps)
    return n_images
