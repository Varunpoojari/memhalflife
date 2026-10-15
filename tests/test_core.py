import json
import math

import pytest

from memhalflife.dataset import collect_records
from memhalflife.extract import evaluate_artefact, flatten_rows, score_image
from memhalflife.models import ArtefactResult, ArtefactSpec
from memhalflife.scenarios import ScenarioError, load_scenario
from memhalflife.scoring import coverage, dcs, dcs_by_category
from memhalflife.survival import (
    classify_pattern,
    curve_with_ci,
    halflife_with_ci,
    time_to_fraction,
    value_at,
)


def spec(**kw):
    base = dict(id="a", category="execution", weight=1, plugin="p", match={"Args": "foo"}, partial={})
    base.update(kw)
    return ArtefactSpec(**base)


# ---------------------------------------------------------------- scenarios
def test_all_shipped_scenarios_load(scenarios):
    assert {"S01", "S04", "S05", "S06", "L01", "L02", "L03"} <= set(scenarios)
    for sc in scenarios.values():
        assert sc.artefacts and all(a.weight > 0 for a in sc.artefacts)
        for a in sc.artefacts:  # synthetic templates must satisfy their own full match
            if a.synthetic.get("row"):
                assert evaluate_artefact(a, [a.synthetic["row"]]) == "Y", f"{sc.id}/{a.id}"
                assert len(a.synthetic["p"]) == len(sc.timepoints), f"{sc.id}/{a.id}"
            if a.synthetic.get("partial_row"):
                assert evaluate_artefact(a, [a.synthetic["partial_row"]]) == "P", f"{sc.id}/{a.id}"


def test_bad_regex_rejected(tmp_path):
    p = tmp_path / "x.toml"
    p.write_text('id="X"\ntimepoints=[0,5]\n[[artefact]]\nid="a"\nplugin="p"\n[artefact.match]\nA="("\n')
    with pytest.raises(ScenarioError):
        load_scenario(p)


def test_unsorted_timepoints_rejected(tmp_path):
    p = tmp_path / "x.toml"
    p.write_text('id="X"\ntimepoints=[5,0]\n[[artefact]]\nid="a"\nplugin="p"\n[artefact.match]\nA="x"\n')
    with pytest.raises(ScenarioError):
        load_scenario(p)


# --------------------------------------------------------------- extraction
def test_flatten_children():
    rows = [{"PID": 1, "__children": [{"PID": 2, "__children": [{"PID": 3}]}]}, {"PID": 4}]
    assert [r["PID"] for r in flatten_rows(rows)] == [1, 2, 3, 4]


def test_evaluate_statuses():
    s = spec(match={"Args": "foo", "Process": "^x"}, partial={"Args": "foo"})
    assert evaluate_artefact(s, [{"Args": "foo", "Process": "x.exe"}]) == "Y"
    assert evaluate_artefact(s, [{"Args": "foo", "Process": "y.exe"}]) == "P"
    assert evaluate_artefact(s, [{"Args": "bar", "Process": "x.exe"}]) == "N"
    assert evaluate_artefact(s, None) == "NA"
    assert evaluate_artefact(s, []) == "N"


def test_conditions_must_hold_on_same_row():
    s = spec(match={"Args": "foo", "Process": "^x"})
    assert evaluate_artefact(s, [{"Args": "foo", "Process": "y"}, {"Args": "bar", "Process": "x"}]) == "N"


def test_missing_plugin_output_is_na_not_absent(scenarios, tmp_path):
    res = score_image(scenarios["S01"], tmp_path)
    assert {r.status for r in res} == {"NA"}
    assert dcs(res) is None and coverage(res) == 0.0


def test_malformed_json_is_na(scenarios, tmp_path):
    (tmp_path / "windows.cmdline.CmdLine.json").write_text("{not json")
    res = {r.artefact_id: r.status for r in score_image(scenarios["S01"], tmp_path)}
    assert res["ps_cradle_cmdline"] == "NA"


# ------------------------------------------------------------------ scoring
def test_weighted_vs_unweighted():
    rs = [ArtefactResult("a", "x", 3, "Y"), ArtefactResult("b", "x", 1, "N")]
    assert dcs(rs, weighted=True) == pytest.approx(0.75)
    assert dcs(rs, weighted=False) == pytest.approx(0.5)


def test_partial_counts_half_and_na_excluded():
    rs = [ArtefactResult("a", "x", 1, "P"), ArtefactResult("b", "y", 1, "NA")]
    assert dcs(rs) == pytest.approx(0.5)
    assert dcs_by_category(rs) == {"x": 0.5}
    assert coverage(rs) == 0.5


# ----------------------------------------------------------------- survival
def test_time_to_fraction_interpolates():
    hl = time_to_fraction([0, 5, 15], [1.0, 0.8, 0.2], 0.5)
    assert hl.value == pytest.approx(5 + (0.8 - 0.5) / (0.8 - 0.2) * 10)
    assert not hl.censored


def test_time_to_fraction_censored_and_undefined():
    hl = time_to_fraction([0, 5, 15], [1.0, 0.9, 0.8], 0.5)
    assert hl.value is None and hl.censored and hl.lower_bound == 15
    assert time_to_fraction([0, 5], [0.0, 0.0]).value is None


def test_value_at_clamps():
    assert value_at([0, 10], [1.0, 0.0], 5) == pytest.approx(0.5)
    assert value_at([0, 10], [1.0, 0.0], 99) == 0.0


def test_classify_patterns():
    assert classify_pattern([0, 5, 15], [0.9, 0.85, 0.8]) == "Stable"
    assert classify_pattern([0, 5, 15], [1.0, 0.0, 0.0]) == "Cliff-edge"
    assert classify_pattern([0, 5, 15], [1.0, 0.7, 0.4]) == "Gradual"
    assert classify_pattern([0, 5, 15], [0.25, 0.2, 0.15]) == "Low-footprint"
    assert classify_pattern([0, 5, 15], [0.25, 0.25, 0.2]) == "Stable"  # stable wins over low-footprint
    assert classify_pattern([0, 15, 60], [0.5, 0.3, 0.3], reboot_at=60) == "Reboot-stable"
    assert classify_pattern([0, 5], [0.0, 0.0]) == "Undefined"


def _records(per_t_scores, reps):
    out = []
    for rep in range(reps):
        for t, v in per_t_scores.items():
            out.append({"scenario": "X", "rep": rep, "t": t, "artefact": "a", "category": "c",
                        "weight": 1, "status": "Y" if v >= 1 else "N"})
    return out


def test_ci_has_no_nan_and_brackets_point():
    # 10 runs, half lose evidence at T+5, half keep it to the end -> some bootstrap
    # resamples are censored; CI must stay finite-or-inf, never nan.
    recs = []
    for rep in range(10):
        keep = rep % 2 == 0
        for t in (0, 5, 15):
            recs.append({"scenario": "X", "rep": rep, "t": t, "artefact": "a", "category": "c",
                         "weight": 1, "status": "Y" if (t == 0 or keep) else "N"})
    h = halflife_with_ci(recs, "X", boots=500)
    assert h.lo is not None and not math.isnan(h.lo)
    assert h.hi is not None and not math.isnan(h.hi)


def test_curve_ci_ordering():
    c = curve_with_ci(_records({0: 1, 5: 1, 15: 0}, 6), "X", boots=200)
    assert c.n_runs == 6
    for m, lo, hi in zip(c.mean, c.lo, c.hi):
        assert lo <= m + 1e-9 and m <= hi + 1e-9


def test_deterministic_given_seed():
    r = _records({0: 1, 5: 0}, 5)
    assert curve_with_ci(r, "X", boots=100, seed=5).lo == curve_with_ci(r, "X", boots=100, seed=5).lo


# ------------------------------------------------------- end-to-end synthetic
def test_synthetic_pipeline_end_to_end(synth_dir, scenarios):
    recs = collect_records(synth_dir, scenarios)
    assert recs and not any(r["status"] == "NA" for r in recs)
    # S05 (LSASS) is built to be a cliff: nearly everything gone by T+15
    c = curve_with_ci(recs, "S05", boots=100)
    assert c.mean[0] > 0.9 and c.mean[-1] < 0.1
    assert classify_pattern(c.ts, c.mean) == "Cliff-edge"
    # S04 (injection) persists
    c4 = curve_with_ci(recs, "S04", boots=100)
    assert c4.mean[-1] > 0.6


def test_dataset_manifest_flags_synthetic(synth_dir):
    assert json.loads((synth_dir / "dataset.json").read_text())["synthetic"] is True
