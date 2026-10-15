# Methodology

## Research question

For a given fileless / LOTL technique, how does the recoverable forensic evidence in physical
memory decay with time after the attack, and what does that imply for memory-acquisition
deadlines?

## Experimental design

1. **Isolated lab.** Victim VM(s) on a host-only or isolated-subnet network; instrumentation
   (e.g. Sysmon on Windows) installed *before* the clean baseline snapshot.
2. **One scenario = one technique**, executed with a benign/lab-safe test (Atomic Red Team
   or an equivalent harmless program) from a reverted baseline.
3. **Replicates.** Repeat each scenario **n ≥ 10** times (n ≥ 5 is a minimum for CIs to mean
   anything). A "run" is one execution imaged at every timepoint.
4. **Timepoints** (minutes after attack completion): default `0, 5, 15, 60`. S06 adds a
   post-reboot image at the last timepoint (`reboot_at`).
5. **Acquisition.** Windows: WinPmem or hypervisor snapshot. Linux/cloud: AVML or LiME. Hash
   immediately (`memhalflife analyse` does this) and record the tool/version.
6. **Analysis.** Identical Volatility 3 plugin set per OS for every image
   (`runner.WINDOWS_PLUGINS` / `LINUX_PLUGINS`), plus optional YARA scan.

### Observer effect — choose one and say which

Imaging the same running VM repeatedly perturbs it (the acquisition tool allocates memory,
may trigger scans, and takes time). Two defensible designs:

- **Serial imaging** (default assumption): one run, images at T+0, T+5, ... Cheap; each image
  perturbs the next. Report this limitation.
- **Independent runs per timepoint:** a fresh run for every timepoint. Cleaner, costs
  `timepoints × n` runs. The bootstrap still works but pairing across timepoints is lost.

## Detection Completeness Score (DCS v2)

For each artefact: `Y = 1.0`, `P = 0.5`, `N = 0`, **`NA`** if the required plugin output is
missing or unreadable (excluded from the score and counted in "not judged").

```
DCS = Σ wᵢ·vᵢ / Σ wᵢ        (over artefacts with a verdict)
```

Weights (documented per artefact in each scenario file):

| Weight | Meaning | Example |
|---|---|---|
| 3 | Direct, high-fidelity evidence of the technique | attacker command line; RWX region in host process |
| 2 | Corroborating | socket owned by the process; DLL loaded |
| 1 | Contextual | process merely listed |

`memhalflife report --unweighted` yields DCS v1 (plain average) for comparison with earlier work.
Weights are a judgement; report sensitivity by running both.

## Decay statistics

- **Curve:** mean DCS per timepoint across runs.
- **Confidence bands:** percentile bootstrap (default 2000 resamples, 95%) resampling **whole
  runs**, preserving within-run correlation. Fixed seed ⇒ reproducible.
- **Half-life:** first time the mean curve falls to 50% of its T+0 value, by linear
  interpolation between timepoints. If it never does, the estimate is **right-censored**
  (reported as `>last timepoint`), not fabricated. CI upper bounds may be `∞` when some
  resamples are censored.
- **Capture window:** same estimator at 80% retention ("capture within X min to keep 80%").
- **Pattern class:** Stable (≥80% retained), Cliff-edge (one drop ≥60% of initial and ≤15%
  retained), Reboot-stable (post-reboot ≥80% of pre-reboot), Low-footprint, else Gradual.
  Heuristic labels for communication; the curves are the result.
- **Per-artefact half-lives** (`artefact_halflife.csv`) show *which* evidence disappears first.

Limitations: few timepoints means interpolation, not a fitted parametric model; a coarse grid
cannot resolve cliffs between timepoints (add early points such as T+1, T+2 if a cliff is
suspected); regex rules measure presence of *expected* artefacts, so unexpected evidence is out
of scope; results are per OS build, tool version and Volatility version.

## Acquisition-SLA model

Acquisition latency (decision → image complete) is lognormal with median *m* and 95th
percentile *p95*. For each draw, retention = `DCS(latency) / DCS(0)` (curve interpolated,
clamped at the last timepoint; the share of draws beyond the observed window is reported as
`extrapolated_share`). Output: expected retention and `P(retention ≥ threshold)`.

Shipped profiles are **placeholders** (`assumed = true`). Measure your own: time your runbook
end to end at least 10 times and put the median and p95 in `profiles/latency.toml`.

## Reproducibility checklist

- Scenario file versions + git commit
- Volatility 3 version, ISF/symbol sources (Linux)
- OS build, kernel version, cloud instance type/region
- Acquisition tool + version
- `custody.jsonl` (hashes) and `dataset.json`
- Random seed for bootstrap (`--boots`, default seed 1337)
