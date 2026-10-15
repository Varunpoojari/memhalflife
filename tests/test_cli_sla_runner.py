import json
import math

import pytest

from memhalflife import cli
from memhalflife.report import build_summaries
from memhalflife.dataset import collect_records
from memhalflife.runner import analyse_image, build_command, custody_record, sha256_file
from memhalflife.sla import LatencyProfile, load_profiles, simulate
from memhalflife.survival import Curve


def test_latency_profile_lognormal_params():
    p = LatencyProfile("x", "", median_min=10, p95_min=40)
    assert p.mu == pytest.approx(math.log(10))
    assert p.sigma == pytest.approx(math.log(4) / 1.6448536, rel=1e-5)


def test_sla_monotone_in_latency():
    curve = Curve("X", [0, 5, 15, 60], [1.0, 0.8, 0.4, 0.1], [1, .8, .4, .1], [1, .8, .4, .1], 5)
    fast = simulate(curve, LatencyProfile("f", "", 2, 4), draws=4000)
    slow = simulate(curve, LatencyProfile("s", "", 30, 90), draws=4000)
    assert fast.expected_retention > slow.expected_retention
    assert fast.p_retain_ge_threshold > slow.p_retain_ge_threshold
    assert slow.extrapolated_share > fast.extrapolated_share


def test_shipped_profiles_are_flagged_assumed(scenarios):
    from pathlib import Path

    profs = load_profiles(Path(__file__).resolve().parents[1] / "profiles" / "latency.toml")
    assert profs and all(p.assumed for p in profs.values())


def test_sha256_and_custody(tmp_path):
    f = tmp_path / "img.raw"
    f.write_bytes(b"abc")
    assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    rec = custody_record(f, scenario="S01")
    assert rec["size_bytes"] == 3 and rec["scenario"] == "S01"


def test_build_command_shape():
    cmd = build_command("python3 vol.py", "/x/img.raw", "windows.pslist.PsList", ["--pid", "4"])
    assert cmd == ["python3", "vol.py", "-q", "-r", "json", "-f", "/x/img.raw", "windows.pslist.PsList", "--pid", "4"]


def test_analyse_missing_vol_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Volatility 3"):
        analyse_image(tmp_path / "i", "windows", tmp_path / "o", vol="definitely-not-installed-vol")


def test_unknown_os_rejected(tmp_path):
    with pytest.raises(ValueError):
        analyse_image(tmp_path / "i", "plan9", tmp_path / "o")


def test_cli_report_writes_outputs(synth_dir, tmp_path, capsys):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    rc = cli.main(["--scenarios", str(root / "scenarios"), "report", "--dataset", str(synth_dir),
                   "--out", str(tmp_path), "--profiles", str(root / "profiles"), "--boots", "100"])
    assert rc == 0
    for name in ("report.md", "report.html", "halflife.csv", "dcs_curves.csv",
                 "artefact_matrix.csv", "artefact_halflife.csv"):
        assert (tmp_path / name).is_file(), name
    md = (tmp_path / "report.md").read_text()
    html = (tmp_path / "report.html").read_text()
    assert "SYNTHETIC DATA" in md and "Synthetic data" in html
    assert "nan" not in md.lower()
    assert "<svg" in html


def test_summaries_cover_all_scenarios(synth_dir, scenarios):
    recs = collect_records(synth_dir, scenarios)
    sums = build_summaries(recs, scenarios, boots=50)
    assert {s.scenario.id for s in sums} == set(scenarios)
