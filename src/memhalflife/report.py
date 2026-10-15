"""Summaries and report rendering (CSV, Markdown, self-contained HTML with SVG)."""

from __future__ import annotations

import csv
import html
import math
from dataclasses import dataclass
from pathlib import Path

from .models import Scenario
from .sla import LatencyProfile, SlaResult, simulate
from .survival import (
    Curve,
    HalfLifeCI,
    artefact_survival,
    classify_pattern,
    curve_with_ci,
    halflife_with_ci,
    time_to_fraction,
)


@dataclass
class ScenarioSummary:
    scenario: Scenario
    curve: Curve
    half: HalfLifeCI
    budget80: HalfLifeCI  # time until retention falls to 80% of initial
    pattern: str
    na_share: float


def build_summaries(
    records: list[dict],
    scenarios: dict[str, Scenario],
    weighted: bool = True,
    boots: int = 2000,
) -> list[ScenarioSummary]:
    out = []
    for sid, sc in scenarios.items():
        recs = [r for r in records if r["scenario"] == sid]
        if not recs:
            continue
        curve = curve_with_ci(records, sid, weighted, boots)
        if not curve.ts:
            continue
        half = halflife_with_ci(records, sid, 0.5, weighted, boots)
        b80 = halflife_with_ci(records, sid, 0.8, weighted, boots)
        na = sum(r["status"] == "NA" for r in recs) / len(recs)
        out.append(
            ScenarioSummary(sc, curve, half, b80, classify_pattern(curve.ts, curve.mean, sc.reboot_at), na)
        )
    return out


def fmt_hl(h: HalfLifeCI) -> str:
    p = h.point
    if p.value is None:
        if not p.censored:
            return "n/a"
        s = f">{p.lower_bound:g} min"
        if h.lo is not None and not math.isinf(h.lo):
            s += f" (CI lower {h.lo:.1f})"
        return s
    s = f"{p.value:.1f} min"
    if h.lo is not None and h.hi is not None:
        hi = "∞" if math.isinf(h.hi) else f"{h.hi:.1f}"
        s += f" (95% CI {h.lo:.1f}–{hi})"
    return s


def write_csvs(out: Path, records: list[dict], summaries: list[ScenarioSummary]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "artefact_matrix.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["scenario", "rep", "t", "artefact", "category", "weight", "status"])
        w.writeheader()
        w.writerows(records)
    with (out / "dcs_curves.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario", "t_min", "dcs_mean", "ci_lo", "ci_hi", "n_runs"])
        for s in summaries:
            for t, m, lo, hi in zip(s.curve.ts, s.curve.mean, s.curve.lo, s.curve.hi):
                w.writerow([s.scenario.id, t, f"{m:.4f}", f"{lo:.4f}", f"{hi:.4f}", s.curve.n_runs])
    with (out / "halflife.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario", "technique", "platform", "pattern", "halflife_min", "ci_lo", "ci_hi",
                    "censored", "t_to_80pct_min", "pct_artefacts_not_judged"])
        for s in summaries:
            p = s.half.point
            w.writerow([
                s.scenario.id, s.scenario.technique, s.scenario.platform, s.pattern,
                "" if p.value is None else f"{p.value:.2f}",
                "" if s.half.lo is None else f"{s.half.lo:.2f}",
                "" if s.half.hi is None else ("inf" if math.isinf(s.half.hi) else f"{s.half.hi:.2f}"),
                p.censored,
                "" if s.budget80.point.value is None else f"{s.budget80.point.value:.2f}",
                f"{100 * s.na_share:.1f}",
            ])
    with (out / "artefact_halflife.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario", "artefact", "category", "weight", "halflife_min", "censored"])
        for s in summaries:
            surv = artefact_survival(records, s.scenario.id)
            for a in s.scenario.artefacts:
                if a.id not in surv:
                    continue
                ts, ys = surv[a.id]
                hl = time_to_fraction(ts, ys, 0.5)
                w.writerow([s.scenario.id, a.id, a.category, a.weight,
                            "" if hl.value is None else f"{hl.value:.2f}", hl.censored])


# ---------------------------------------------------------------- SVG charts
def decay_svg(summaries: list[ScenarioSummary], cols: int = 3) -> str:
    pw, ph, pad = 330, 200, 14
    rows = math.ceil(len(summaries) / cols)
    W, H = cols * (pw + pad) + pad, rows * (ph + pad) + pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="DCS decay per scenario" font-family="system-ui,sans-serif" font-size="11">'
    ]
    for i, s in enumerate(summaries):
        ox = pad + (i % cols) * (pw + pad)
        oy = pad + (i // cols) * (ph + pad)
        l, r, t, b = 38, 12, 28, 30
        x0, x1, y0, y1 = ox + l, ox + pw - r, oy + t, oy + ph - b
        n = len(s.curve.ts)

        def X(k: int) -> float:
            return x0 + (x1 - x0) * (k / (n - 1 if n > 1 else 1))

        def Y(v: float) -> float:
            return y1 - (y1 - y0) * max(0.0, min(1.0, v))

        color = "#1f6feb" if s.scenario.platform == "windows" else "#d97706"
        parts.append(f'<g><rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" rx="6" fill="none" stroke="#8884"/>')
        title = html.escape(f"{s.scenario.id} · {s.scenario.technique} · {s.pattern}")
        parts.append(f'<text x="{ox + 10}" y="{oy + 18}" font-weight="600" fill="currentColor">{title}</text>')
        for g in (0, 0.5, 1):
            parts.append(f'<line x1="{x0}" x2="{x1}" y1="{Y(g)}" y2="{Y(g)}" stroke="#8883"/>')
            parts.append(f'<text x="{x0 - 5}" y="{Y(g) + 4}" text-anchor="end" fill="currentColor">{int(g * 100)}%</text>')
        band = [f"{X(k):.1f},{Y(s.curve.hi[k]):.1f}" for k in range(n)] + [
            f"{X(k):.1f},{Y(s.curve.lo[k]):.1f}" for k in reversed(range(n))
        ]
        parts.append(f'<polygon points="{" ".join(band)}" fill="{color}" opacity="0.18"/>')
        line = " ".join(f"{X(k):.1f},{Y(s.curve.mean[k]):.1f}" for k in range(n))
        parts.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        for k in range(n):
            parts.append(f'<circle cx="{X(k):.1f}" cy="{Y(s.curve.mean[k]):.1f}" r="3.2" fill="{color}"/>')
            tl = f"T+{s.curve.ts[k]:g}"
            parts.append(f'<text x="{X(k):.1f}" y="{y1 + 16}" text-anchor="middle" fill="currentColor">{tl}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- Markdown / HTML
def _banner(synthetic: bool) -> str:
    return (
        "**SYNTHETIC DATA — pipeline demonstration only. These numbers are not research findings.**\n\n"
        if synthetic
        else ""
    )


def render_markdown(
    summaries: list[ScenarioSummary],
    sla: list[SlaResult],
    profiles: dict[str, LatencyProfile],
    synthetic: bool,
    weighted: bool,
) -> str:
    L = ["# MemHalfLife report\n", _banner(synthetic)]
    L.append(f"Scoring: {'weighted DCS v2' if weighted else 'unweighted DCS v1'}; "
             "95% bootstrap CIs resample whole attack runs.\n")
    L.append("## Evidence half-life by scenario\n")
    L.append("| Scenario | Technique | Platform | Pattern | DCS T+0 → last | Half-life | Capture within (80% kept) | Runs |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in summaries:
        L.append(
            f"| {s.scenario.id} {s.scenario.name} | {s.scenario.technique} | {s.scenario.platform} | {s.pattern} | "
            f"{s.curve.mean[0]:.0%} → {s.curve.mean[-1]:.0%} | {fmt_hl(s.half)} | {fmt_hl(s.budget80)} | {s.curve.n_runs} |"
        )
    if sla:
        L.append("\n## Expected evidence recovered, by acquisition-latency profile\n")
        assumed = [p.id for p in profiles.values() if p.assumed]
        if assumed:
            L.append("> Latency profiles marked *assumed* are illustrative placeholders; replace with measured values.\n")
        names = sorted({r.profile for r in sla})
        L.append("| Scenario | " + " | ".join(names) + " |")
        L.append("|---|" + "---|" * len(names))
        by = {(r.scenario, r.profile): r for r in sla}
        for s in summaries:
            cells = []
            for n in names:
                r = by.get((s.scenario.id, n))
                cells.append("–" if r is None or math.isnan(r.expected_retention)
                             else f"{r.expected_retention:.0%} (P≥{r.threshold:.0%}: {r.p_retain_ge_threshold:.0%})")
            L.append(f"| {s.scenario.id} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def render_html(
    summaries: list[ScenarioSummary],
    sla: list[SlaResult],
    profiles: dict[str, LatencyProfile],
    synthetic: bool,
    weighted: bool,
) -> str:
    esc = html.escape
    rows = "".join(
        f"<tr><td>{esc(s.scenario.id)} {esc(s.scenario.name)}</td><td>{esc(s.scenario.technique)}</td>"
        f"<td>{esc(s.scenario.platform)}</td><td>{esc(s.pattern)}</td>"
        f"<td>{s.curve.mean[0]:.0%} → {s.curve.mean[-1]:.0%}</td><td>{esc(fmt_hl(s.half))}</td>"
        f"<td>{esc(fmt_hl(s.budget80))}</td><td>{s.curve.n_runs}</td></tr>"
        for s in summaries
    )
    sla_html = ""
    if sla:
        names = sorted({r.profile for r in sla})
        by = {(r.scenario, r.profile): r for r in sla}
        head = "".join(f"<th>{esc(n)}</th>" for n in names)
        body = ""
        for s in summaries:
            cells = ""
            for n in names:
                r = by.get((s.scenario.id, n))
                cells += "<td>–</td>" if r is None or math.isnan(r.expected_retention) else (
                    f"<td>{r.expected_retention:.0%} <small>(P≥{r.threshold:.0%}: {r.p_retain_ge_threshold:.0%})</small></td>"
                )
            body += f"<tr><td>{esc(s.scenario.id)}</td>{cells}</tr>"
        note = (
            "<p class='note'>Latency profiles flagged <em>assumed</em> are illustrative placeholders — "
            "replace with measured values.</p>" if any(p.assumed for p in profiles.values()) else ""
        )
        sla_html = (
            f"<h2>Expected evidence recovered by acquisition latency</h2>{note}"
            f"<table><thead><tr><th>Scenario</th>{head}</tr></thead><tbody>{body}</tbody></table>"
        )
    banner = (
        "<div class='warn'><strong>Synthetic data.</strong> Pipeline demonstration only — not research findings.</div>"
        if synthetic else ""
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MemHalfLife report</title>
<style>
:root{{color-scheme:light dark;--bg:#fff;--fg:#1b1f24;--mut:#5b6570;--line:#d0d7de;--warn:#fff4ce}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#9aa4ae;--line:#30363d;--warn:#3a2f0b}}}}
body{{margin:0 auto;max-width:1100px;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
th,td{{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
.warn{{background:var(--warn);padding:10px 14px;border-radius:6px;margin:12px 0}}
.note,small{{color:var(--mut)}} svg{{width:100%;height:auto;color:var(--fg)}}
</style></head><body>
<h1>MemHalfLife report</h1>{banner}
<p>Scoring: {'weighted DCS v2' if weighted else 'unweighted DCS v1'}. Shaded bands are 95% bootstrap CIs
(runs resampled); x-axis is ordinal, not to scale.</p>
{decay_svg(summaries)}
<h2>Evidence half-life by scenario</h2>
<table><thead><tr><th>Scenario</th><th>Technique</th><th>Platform</th><th>Pattern</th><th>DCS T+0 → last</th>
<th>Half-life</th><th>Capture within (80% kept)</th><th>Runs</th></tr></thead><tbody>{rows}</tbody></table>
{sla_html}</body></html>"""


def run_sla(
    summaries: list[ScenarioSummary], profiles: dict[str, LatencyProfile], threshold: float = 0.8
) -> list[SlaResult]:
    return [simulate(s.curve, p, threshold) for s in summaries for p in profiles.values()]
