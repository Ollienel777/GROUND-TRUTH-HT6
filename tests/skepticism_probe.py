"""Skepticism-gate probe (dev tooling — NOT part of the submission).

Names the assumption under test and varies THAT dimension. The gate's hidden
assumption was that `replication_count` and `independent_groups` are
interchangeable support — but the skepticism axis is about INDEPENDENCE. So we
hold independence low and vary internal replication (must still hold), and vary
independence across the 1->2 boundary (must flip hold->revise).

A single source is one that has not been independently reproduced: many internal
repeats by one lab are not independent confirmation of an extraordinary claim.

Run:  python3 tests/skepticism_probe.py
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
from groundtruth.model import GraphView
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest

# Extraordinary contradiction of an established claim (C3c ~0.92, "cannot return
# to pluripotency by defined factors").
REPRO = "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state."


def P(groups, repl, effect="strong", direct="direct"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": "defined_factor_perturbation",
            "method_directness": direct, "effect_strength": effect, "retraction_status": "none"}


# (name, provenance, want)  want in {"hold","revise"}
CASES = [
    ("SG1 groups=1, repl=1        single source, unreplicated", P(1, 1), "hold"),
    ("SG2 groups=1, repl=many     single source, many internal repeats", P(1, "many"), "hold"),
    ("SG3 groups=0, repl=many     no independent groups", P(0, "many"), "hold"),
    ("SG4 groups=2, repl=1        independent (boundary) -> revise", P(2, 1), "revise"),
    ("SG5 groups=5, repl=many     strongly independent -> revise", P(5, "many"), "revise"),
    ("SG6 groups=few, repl=several word-valued independent -> revise", P("few", "several"), "revise"),
]


def main():
    print("=" * 74)
    print("SKEPTICISM-GATE PROBE  (independence, not raw counts, gates the hold)")
    print("=" * 74)
    reds = []
    for name, prov, want in CASES:
        g = load_seed()
        r = ingest(EvidenceItem("SG", "", REPRO, prov), GraphView(g))
        ops = [d.op for d in r.deltas]
        revised = "revise_confidence" in ops
        held = ("hold_pending" in ops) and not revised
        ok = held if want == "hold" else revised
        if not ok:
            reds.append(name)
        print(f"  {'PASS' if ok else 'FAIL':4}  want={want:6} {name}")
        print(f"        ops={ops}")
    print("-" * 74)
    print(f"  {len(CASES) - len(reds)}/{len(CASES)} pass" + ("" if not reds else f"  |  RED: {[n.split()[0] for n in reds]}"))
    print("=" * 74)


if __name__ == "__main__":
    main()
