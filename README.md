# MemHalfLife

**Quantifying how long fileless and living-off-the-land attack evidence survives in memory — on-prem and in the cloud.**

Incident responders are told to "grab memory fast", but not *how* fast. MemHalfLife turns that
into a number per technique: it scores Volatility 3 output at fixed times after an attack, fits
decay curves with bootstrap confidence intervals, and combines them with your measured
acquisition latency to say **how much evidence you should expect to recover**.

> **Status: v0.1 — tooling complete, real lab data pending.**
> Any report built from `memhalflife synth` is **synthetic** and flagged as such. The scenario
> library, scoring and statistics are tested; the research results come when you run the lab
> (see [docs/METHODOLOGY.md](docs/METHODOLOGY.md)).

## What's new compared with earlier manual workflows

| Area | Manual / earlier approach | MemHalfLife |
|---|---|---|
| Analysis | Batch file + hand-filled artefact matrix | Declarative TOML scenarios → automatic Y/P/N judgement from Volatility 3 JSON |
| Metric | Simple Y/P/N average | **Weighted DCS v2** (+ v1 for comparability); unjudgeable artefacts are `NA`, never silently "absent" |
| Statistics | Single run per point | Replicate runs, **bootstrap 95% CIs** (resampling whole runs), right-censoring handled |
| Output | Point percentages | **Evidence half-life**, time-to-80%-retained, decay pattern class (Stable / Cliff-edge / Gradual / Reboot-stable) |
| Platform | Windows only | **Windows + Linux cloud VMs** (memfd fileless ELF, IMDS credential access, `/dev/tcp` shells) |
| IR guidance | Qualitative | **Acquisition-SLA simulator**: decay curve × latency distribution → expected recovery per technique |
| Integrity | Manual hashing | Automatic SHA-256 + append-only custody log; synthetic data self-labelling |

## Quick start

```bash
pip install -e ".[dev,yara]"
pytest                                   # 41 tests

memhalflife scenarios                    # list the 9 shipped scenarios
memhalflife synth --out demo --reps 10   # SYNTHETIC dataset to exercise the pipeline
memhalflife report --dataset demo --out demo_report
open demo_report/report.html             # decay charts, half-lives, SLA table
```

With real images (needs [Volatility 3](https://github.com/volatilityfoundation/volatility3)):

```bash
memhalflife analyse --image s01_run3_t5.raw --dataset runs \
    --scenario S01 --rep 3 --t 5 --yara rules/yara/memhalflife.yar \
    --analyst "V. Poojari" --acq-tool "WinPmem 4.0"
memhalflife report --dataset runs --out results
```

## Scenarios

| ID | Technique | Platform | What decays |
|---|---|---|---|
| S01 | T1059.001 PowerShell download cradle | Windows | cmdline, process, socket, AMSI |
| S02 | T1218.005 mshta proxy execution | Windows | short-lived helper process |
| S03 | T1218.010 regsvr32 scriptlet | Windows | cmdline, `scrobj.dll`, socket |
| S04 | T1055 process injection | Windows | RWX region, hollowing, threads, socket |
| S05 | T1003.001 LSASS access | Windows | handles, privileges, tool cmdline |
| S06 | T1546.003 WMI subscription (+ reboot) | Windows | consumer strings, `scrcons`, creation cmdline |
| L01 | T1620 memfd fileless ELF | Linux / cloud VM | memfd mapping, fd, argv |
| L02 | T1552.005 IMDS credential access | Linux / cloud VM | shell history vs curl argv vs socket |
| L03 | T1059.004 `/dev/tcp` reverse shell | Linux / cloud VM | history, shell argv, socket |

Add your own by dropping a TOML file in `scenarios/` — see any shipped file for the format.

## Layout

```
scenarios/   declarative technique definitions (artefacts, weights, regex conditions)
profiles/    acquisition-latency profiles (placeholders — measure your own)
rules/yara/  8 detection rules, positive + benign-tested
src/memhalflife/  extract · scoring · survival · sla · runner · report · cli
docs/        METHODOLOGY · CLOUD_ACQUISITION · ATTRIBUTION
```

## Safety and scope

Defensive research tool. It *reads* memory images and never generates or runs attack payloads.
Scenario notes point to Atomic Red Team tests and require an isolated lab with harmless test
programs. Do not run attack simulations on systems you do not own.

MIT licensed.
