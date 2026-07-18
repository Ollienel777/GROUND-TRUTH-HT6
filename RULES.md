# Rules

**Language / runtime.** Python 3.10+. The standard library is sufficient. If the
organizers provide a shared model endpoint, you may call it from inside `ingest`;
no other network access is assumed during evaluation.

**What you edit.** Only `starter/my_solution.py` (and any helper modules you add
and import from it). Do not modify anything under `groundtruth/`; at judging your
`ingest` is run against the official framework and a hidden stream.

**The contract.** Your `ingest(item, view)` must return an `IngestResult`. The
belief state changes only through the `Delta` objects you return. `item.tag` is
empty at runtime. Reading it, or attempting to read any hidden test data, is not
a strategy; it is not in the repo.

**Determinism.** Your solution should be deterministic given the same inputs. If
you call an LLM, handle timeouts and malformed responses gracefully; a crash on an
item scores that item as a no-op.

**Teams.** 1–4 people. One submission per team: your repo fork with
`starter/my_solution.py` filled in, plus a short `DESIGN.md` (max one page)
describing your evidence-weighting model and how you enforce the firewall.

**Judging.** Automated, against a hidden evidence stream, on four axes: firewall
integrity (pass/fail gate), revision correctness (40), robustness to false
evidence (25), out-of-distribution detection (35). 
