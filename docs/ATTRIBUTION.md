# Attribution and provenance

MemHalfLife was inspired by the research question explored in the public repository
[`tanishqbapna/lotl-memory-forensics`](https://github.com/tanishqbapna/lotl-memory-forensics)
(an MSc thesis project at the National College of Ireland: how long does forensic evidence of
fileless / LOTL attacks survive in memory?).

What this project is:

- An **independent re-implementation and extension**, written from scratch. No code, text,
  data, charts or memory images from that repository are included.
- A different structure: declarative scenarios, automated judging, weighted scoring,
  bootstrap statistics, cloud/Linux scenarios and an acquisition-SLA model.

What it is not:

- It does **not** reproduce or validate the original thesis's findings. Any comparison of
  results must come from running both methods on real data.

Good practice when you publish:

1. Credit the original repository and author in your README/paper (done above; keep it).
2. Consider messaging the original author. Collaboration or a comparison study is usually
   welcome, and it avoids any appearance of passing the idea off as new.
3. Never present synthetic output (`dataset.json` has `"synthetic": true`) as results.
4. The original thesis report and manual are the author's academic work; cite them, do not copy.
