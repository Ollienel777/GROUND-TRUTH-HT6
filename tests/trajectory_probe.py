"""Cumulative-trajectory probe (dev tooling — NOT part of the submission).

Single-item probes can't catch drift. These run MULTI-item streams and assert the
*shape* of a claim's confidence over time:
  T1  noise does not creep        — repeated weak evidence stays flat
  T2  legitimate accumulation     — repeated moderate evidence erodes monotonically, bounded
  T3  no rebound after a big drop — weak evidence after a strong result neither recovers nor re-collapses

Run:  python3 tests/trajectory_probe.py
"""
from __future__ import annotations
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groundtruth.loader import load_seed
from groundtruth.harness import run
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest

BODY = "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state."


def P(groups, repl, direct="direct", effect="strong"):
    return {"replication_count": repl, "independent_groups": groups,
            "method_class": "defined_factor_perturbation", "method_directness": direct,
            "effect_strength": effect, "retraction_status": "none"}


def trajectory(provs, claim="C3c"):
    stream = [EvidenceItem(f"T{i}", "", BODY, p) for i, p in enumerate(provs)]
    g = load_seed()
    initial = g.claims[claim].confidence
    log = run(stream, ingest, g)
    return initial, [rec.conf_snapshot.get(claim) for rec in log.records]


def _strictly_decreasing(xs):
    return all(a > b for a, b in zip(xs, xs[1:]))


def main():
    checks = []

    # T1 — noise (weak, indirect) x5 should stay flat near the prior
    init, t1 = trajectory([P(2, 1, direct="indirect", effect="weak")] * 5)
    flat = all(abs(v - init) <= 0.02 for v in t1)
    checks.append(("T1 noise does not creep (5x weak -> flat)", flat, f"init={init:.3f} traj={[round(v,3) for v in t1]}"))

    # T2 — moderate corroboration x4 should erode monotonically, bounded, not overshoot
    init, t2 = trajectory([P(3, 2, effect="moderate")] * 4)
    mono = _strictly_decreasing([init] + t2) and 0.02 < t2[-1] < 0.6
    checks.append(("T2 moderate accumulation erodes monotonically & bounded", mono, f"init={init:.3f} traj={[round(v,3) for v in t2]}"))

    # T3 — one strong drop, then weak noise: big first drop, then flat (no rebound / re-collapse)
    init, t3 = trajectory([P("many", 5, effect="strong")] + [P(2, 1, direct="indirect", effect="weak")] * 3)
    big_then_flat = t3[0] < 0.6 and all(abs(v - t3[0]) <= 0.02 for v in t3[1:])
    checks.append(("T3 strong drop then weak -> no rebound", big_then_flat, f"init={init:.3f} traj={[round(v,3) for v in t3]}"))

    print("=" * 72)
    print("TRAJECTORY PROBE  (cumulative confidence shape over a stream)")
    print("=" * 72)
    n = 0
    for name, ok, detail in checks:
        n += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    print("-" * 72)
    print(f"  {n}/{len(checks)} trajectory checks pass")
    print("=" * 72)
    sys.exit(1 if n != len(checks) else 0)


if __name__ == "__main__":
    main()
