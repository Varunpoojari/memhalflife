# Cloud memory acquisition notes

Memory forensics in the cloud differs from on-prem in three ways that matter for evidence
half-life: **who can reach the host**, **how long acquisition takes**, and **what the platform
can snapshot**.

## What the platform can and cannot snapshot

Disk/volume snapshots (EBS, managed-disk and persistent-disk snapshots) capture **storage, not
RAM**. For memory you need one of:

| Approach | Typical use | Notes |
|---|---|---|
| In-guest acquisition tool | Linux: AVML or LiME; Windows: WinPmem | Needs remote execution on the instance (SSM Run Command, Azure Run Command, OS Login/SSH). Upload the image to restricted storage and hash it. |
| Hibernation-based capture | Some platforms write RAM to disk on hibernate | Changes instance state and is platform-specific: verify behaviour for your provider before relying on it. |
| Hypervisor-level snapshot | Not generally available to tenants on public cloud | Common on-prem (VMware/Hyper-V); used as the on-prem baseline here. |
| Agent-triggered capture | EDR / IR platforms | Latency depends on agent check-in interval. |

## Preparing for Volatility 3 on Linux

Linux analysis needs a symbol table (ISF) matching the **exact kernel** of the instance. Build
or fetch it *in advance* for your standard images (e.g. with `dwarf2json` from the matching
debug symbols) — missing symbols at incident time is a common reason acquisitions go unused.

## Measure your own latency (feeds `profiles/latency.toml`)

Record UTC timestamps for each response, at least 10 times in a drill:

1. `T_detect` — alert fires
2. `T_decide` — responder decides to acquire memory
3. `T_cmd` — acquisition command issued
4. `T_done` — image written and hashed

Latency = `T_done − T_decide` (also useful: `T_decide − T_detect`, which is often the largest
term and the one process changes can shrink). Put the **median** and **95th percentile** into a
new profile and rerun `memhalflife report`.

## Handling and hygiene

- Acquire to a bucket/container with restricted access; enable object versioning/immutability.
- Hash on the instance *and* after transfer; log both (`custody.jsonl`).
- Memory images contain credentials and secrets (including cloud role tokens): encrypt at rest,
  restrict access, and rotate any credentials that were resident.
- Run lab attack tests only in accounts/subscriptions you own, with minimal-permission roles.

## Cloud-specific hypothesis worth testing (L02)

Metadata-service credential access leaves artefacts with very different lifetimes: the `curl`
process and socket are short-lived, while shell history held by a long-running interactive shell
may persist much longer. If the lab confirms this, the practical advice is *"read bash history
from memory even when the process list looks clean"* — and the per-artefact half-lives
(`artefact_halflife.csv`) will show it directly.
