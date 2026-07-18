"""OOD sub-type accuracy probe (dev tooling — NOT part of the submission).

We already flag OOD correctly; this checks we pick the RIGHT sub-type and name:
  regimes_not_modeled -> propose_regime {lateral_somatic_conversion | identity_preserving_state_change}
  axes_excluded       -> propose_axis   {biological_age | cell_function_independent_of_identity}

Run:  python3 tests/ood_subtype_probe.py
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


def P(groups="several", repl="several", method="observational", effect="moderate"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": "direct", "effect_strength": effect, "retraction_status": "none"}


# (name, body, want_op, want_name_substring)
CASES = [
    ("O1 lateral terminal->terminal (distinct germ layers)",
     "A factor converted Fibroblast cells directly into Neuron cells without any intermediate. Reproducible.",
     "propose_regime", "lateral"),
    ("O2 biological age axis",
     "Treated Fibroblasts showed reduced biological age while remaining Fibroblasts. Reproducible.",
     "propose_axis", "age"),
    ("O3 function-without-identity axis (clear function word)",
     "Cells increased their contractile function while their identity was unchanged. Reproducible.",
     "propose_axis", "function"),
    ("O4 function-without-identity, phrased without a function keyword",
     "Cells improved their working output while their cell type was unchanged. Reproducible.",
     "propose_axis", "function"),
    ("O5 identity-preserving STATE change (transition, not a property)",
     "Cells switched between two epigenetic states while their identity was preserved. Reproducible.",
     "propose_regime", "identity_preserving"),
    ("O6 lateral within the same germ layer",
     "A factor transdifferentiated Fibroblast directly into SkeletalMuscleCell. Reproducible.",
     "propose_regime", "lateral"),
]


def main():
    print("=" * 72)
    print("OOD SUB-TYPE PROBE  (right op + right name, not just ood_flag)")
    print("=" * 72)
    n = 0
    for name, body, want_op, want_name in CASES:
        g = load_seed()
        r = ingest(EvidenceItem(name.split()[0], "", body, P()), GraphView(g))
        ops = {d.op: d.payload for d in r.deltas}
        got_op = next((op for op in ("propose_axis", "propose_regime") if op in ops), None)
        got_name = ""
        if got_op:
            got_name = ops[got_op].get("axis") or ops[got_op].get("regime") or ""
        ok = r.ood_flag and got_op == want_op and want_name in got_name
        n += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        want: {want_op}(...{want_name}...)   got: ood={r.ood_flag} {got_op}({got_name})")
    print("-" * 72)
    print(f"  {n}/{len(CASES)} sub-type checks pass")
    print("=" * 72)
    sys.exit(0 if n == len(CASES) else 1)


if __name__ == "__main__":
    main()
