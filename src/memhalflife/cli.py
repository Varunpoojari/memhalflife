"""memhalflife command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .dataset import collect_records, read_manifest, slot_dir
from .report import build_summaries, render_html, render_markdown, run_sla, write_csvs
from .runner import PLUGINS, analyse_image, append_custody, custody_record, sha256_file
from .scenarios import ScenarioError, load_all
from .sla import load_profiles
from .synthetic import generate


def _find_dir(explicit: str | None, name: str) -> Path:
    if explicit:
        return Path(explicit)
    for cand in (Path.cwd() / name, Path(__file__).resolve().parents[2] / name):
        if cand.is_dir():
            return cand
    raise SystemExit(f"could not find a '{name}/' directory; pass --{name}")


def _scenarios(args):
    try:
        return load_all(_find_dir(args.scenarios, "scenarios"))
    except ScenarioError as exc:
        raise SystemExit(f"scenario error: {exc}")


def cmd_scenarios(args) -> int:
    for sc in _scenarios(args).values():
        print(f"{sc.id:4} {sc.platform:8} {sc.technique:11} {sc.name}  [{len(sc.artefacts)} artefacts, t={list(sc.timepoints)}]")
    return 0


def cmd_hash(args) -> int:
    for img in args.images:
        print(f"{sha256_file(img)}  {img}")
    return 0


def cmd_synth(args) -> int:
    n = generate(args.out, _scenarios(args), reps=args.reps, seed=args.seed)
    print(f"wrote {n} synthetic image folders to {args.out} (dataset flagged synthetic)")
    return 0


def cmd_analyse(args) -> int:
    scenarios = _scenarios(args)
    if args.scenario not in scenarios:
        raise SystemExit(f"unknown scenario {args.scenario}; try `memhalflife scenarios`")
    out = slot_dir(args.dataset, args.scenario, args.rep, args.t)
    rec = custody_record(args.image, scenario=args.scenario, rep=str(args.rep), t_min=args.t,
                         analyst=args.analyst or "", acquisition_tool=args.acq_tool or "")
    append_custody(Path(args.dataset) / "custody.jsonl", rec)
    print(f"sha256 {rec['sha256']}  ({rec['size_bytes']} bytes) -> custody.jsonl")
    runs = analyse_image(args.image, scenarios[args.scenario].platform, out, vol=args.vol, yara_file=args.yara)
    ok = sum(r.ok for r in runs)
    for r in runs:
        print(f"  {'ok ' if r.ok else 'FAIL'} {r.plugin} ({r.seconds:.0f}s) {r.detail}")
    print(f"{ok}/{len(runs)} plugins succeeded -> {out}")
    return 0 if ok else 1


def _load(args):
    scenarios = _scenarios(args)
    records = collect_records(args.dataset, scenarios)
    if not records:
        raise SystemExit(f"no scored images found under {args.dataset}")
    return scenarios, records, bool(read_manifest(args.dataset).get("synthetic", False))


def cmd_report(args) -> int:
    scenarios, records, synthetic = _load(args)
    weighted = not args.unweighted
    summaries = build_summaries(records, scenarios, weighted=weighted, boots=args.boots)
    profiles = {}
    try:
        profiles = load_profiles(_find_dir(args.profiles, "profiles") / "latency.toml")
    except (SystemExit, FileNotFoundError):
        print("note: no latency profiles found; skipping SLA section", file=sys.stderr)
    sla = run_sla(summaries, profiles, args.threshold) if profiles else []
    out = Path(args.out)
    write_csvs(out, records, summaries)
    (out / "report.md").write_text(render_markdown(summaries, sla, profiles, synthetic, weighted))
    (out / "report.html").write_text(render_html(summaries, sla, profiles, synthetic, weighted))
    unjudged = sum(r["status"] == "NA" for r in records)
    print(f"{len(records)} artefact observations, {len(summaries)} scenarios -> {out}/")
    if unjudged:
        print(f"warning: {unjudged} observations could not be judged (missing plugin output)", file=sys.stderr)
    if synthetic:
        print("note: dataset is SYNTHETIC; report carries a banner")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="memhalflife", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--scenarios", help="directory of scenario .toml files (default ./scenarios)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scenarios", help="list scenarios").set_defaults(fn=cmd_scenarios)

    p = sub.add_parser("hash", help="SHA-256 memory images")
    p.add_argument("images", nargs="+")
    p.set_defaults(fn=cmd_hash)

    p = sub.add_parser("synth", help="generate a SYNTHETIC dataset to exercise the pipeline")
    p.add_argument("--out", required=True)
    p.add_argument("--reps", type=int, default=10)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=cmd_synth)

    p = sub.add_parser("analyse", help=f"hash + run Volatility 3 plugins on one image ({', '.join(PLUGINS)})")
    p.add_argument("--image", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--rep", required=True)
    p.add_argument("--t", type=float, required=True, help="minutes after attack completion")
    p.add_argument("--vol", default="vol", help="Volatility 3 command (default: vol)")
    p.add_argument("--yara", help="YARA rules file for the memory yarascan plugin")
    p.add_argument("--analyst")
    p.add_argument("--acq-tool", help="e.g. 'WinPmem 4.0', 'AVML 0.14'")
    p.set_defaults(fn=cmd_analyse)

    p = sub.add_parser("report", help="score dataset, estimate half-lives, write CSV/MD/HTML")
    p.add_argument("--dataset", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--profiles", help="directory containing latency.toml (default ./profiles)")
    p.add_argument("--threshold", type=float, default=0.8, help="retention target for SLA (default 0.8)")
    p.add_argument("--boots", type=int, default=2000)
    p.add_argument("--unweighted", action="store_true", help="use v1 Y/P/N average instead of weighted DCS v2")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
