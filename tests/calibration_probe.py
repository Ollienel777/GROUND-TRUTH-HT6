"""Calibration sweep (dev tooling — NOT part of the submission).

#3: instead of spot-checking a dozen provenance points, sweep each dimension and
assert the update magnitude is monotone and sensibly ordered across the whole
space, plus the end-to-end (post-gate) behavior and the secondary magnitudes.
Named assumptions A1..A9 (see the header of each check).

Run:  python3 tests/calibration_probe.py
"""
from __future__ import annotations
import math
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starter.my_solution import strength, ingest, MAX_MOVE, EPS
from groundtruth.loader import load_seed
from groundtruth.harness import run
from groundtruth.model import GraphView
from groundtruth.ingest import EvidenceItem

REPRO = "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state."


def P(groups, repl, effect="strong", direct="direct", retr="none", method="defined_factor_perturbation"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


def S(**kw):
    return strength(P(**kw))


def _L(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def nondec(seq):
    return all(a <= b + 1e-9 for a, b in zip(seq, seq[1:]))


def applied_move(prov, claim="C3c"):
    """End-to-end |Δlogit| the pipeline actually applies to `claim`."""
    g = load_seed()
    before = g.claims[claim].confidence
    rec = run([EvidenceItem("X", "", REPRO, prov)], ingest, g).records[0]
    after = rec.conf_snapshot.get(claim, before)
    return abs(_L(after) - _L(before))


def main():
    checks = []

    # A1..A4 — monotone non-decreasing in each dimension (strength() sweep)
    a1 = [S(groups=g, repl=2) for g in [0, 1, 2, 3, 4, 6]]
    checks.append(("A1 monotone in independent_groups", nondec(a1), [round(x, 3) for x in a1]))
    a2 = [S(groups=3, repl=r) for r in [0, 1, 2, 3, 4, 6]]
    checks.append(("A2 monotone in replication_count", nondec(a2), [round(x, 3) for x in a2]))
    a3 = [S(groups=3, repl=2, effect=e) for e in ["none", "weak", "modest", "moderate", "strong"]]
    checks.append(("A3 monotone in effect_strength", nondec(a3), [round(x, 3) for x in a3]))
    a4 = [S(groups=3, repl=2, direct=d) for d in ["correlational", "inferred", "indirect", "direct"]]
    checks.append(("A4 monotone in method_directness", nondec(a4), [round(x, 3) for x in a4]))

    # A5 — independence dominates replication
    base, g_up, r_up = S(groups=2, repl=2), S(groups=3, repl=2), S(groups=2, repl=3)
    checks.append(("A5 independence dominates replication", (g_up - base) >= (r_up - base),
                   f"Δgroups={g_up-base:.3f} >= Δrepl={r_up-base:.3f}"))

    # A6 — endpoints
    big = MAX_MOVE * S(groups="many", repl="many", effect="strong", direct="direct")
    noise = MAX_MOVE * S(groups=2, repl=1, effect="weak", direct="indirect")
    checks.append(("A6a max provenance -> large move (>=2.0)", big >= 2.0, f"Δlogit={big:.2f}"))
    checks.append(("A6b weak+indirect non-thin -> no_op (<EPS)", noise < EPS, f"Δlogit={noise:.3f} (EPS={EPS})"))

    # A7 — retraction overrides everything
    g = load_seed()
    r = ingest(EvidenceItem("X", "", REPRO, P(groups="many", repl=5, retr="retracted")), GraphView(g))
    a7 = not any(d.op == "revise_confidence" for d in r.deltas)
    checks.append(("A7 retracted strong contradiction -> no revise", a7, [d.op for d in r.deltas]))

    # A8 — secondary (complement) raise subordinate to primary drop
    g2 = load_seed()
    before = {c: g2.claims[c].confidence for c in ("C3c", "C4")}
    rec = run([EvidenceItem("X", "", REPRO, P(groups="many", repl="many"))], ingest, g2).records[0]
    after = rec.conf_snapshot
    d_prim = abs(_L(after["C3c"]) - _L(before["C3c"]))
    d_comp = abs(_L(after["C4"]) - _L(before["C4"]))
    checks.append(("A8 complement raise subordinate to primary drop", 0.0 < d_comp < d_prim,
                   f"primary|Δ|={d_prim:.2f} complement|Δ|={d_comp:.2f}"))

    # A9 — END-TO-END (post-gate) effective move is monotone across weak->strong
    spectrum = [
        P(groups=2, repl=1, effect="weak", direct="indirect"),   # noise -> ~0
        P(groups=2, repl=2, effect="moderate"),                  # low-moderate
        P(groups=3, repl=3, effect="moderate"),                  # moderate
        P(groups=4, repl="several", effect="strong"),            # strong-ish
        P(groups="many", repl="many", effect="strong"),          # max
    ]
    moves = [applied_move(p) for p in spectrum]
    checks.append(("A9 end-to-end effective |Δlogit| monotone (weak->strong)", nondec(moves),
                   [round(m, 2) for m in moves]))

    print("=" * 76)
    print("CALIBRATION SWEEP  (monotone + sensibly-ordered across the provenance space)")
    print("=" * 76)
    reds = []
    for name, ok, detail in checks:
        if not ok:
            reds.append(name)
        print(f"  {'PASS' if ok else 'FAIL':4}  {name}")
        print(f"        {detail}")
    print("-" * 76)
    print(f"  {len(checks) - len(reds)}/{len(checks)} pass" + ("" if not reds else f"  |  RED: {[n.split()[0] for n in reds]}"))
    print("=" * 76)


if __name__ == "__main__":
    main()
