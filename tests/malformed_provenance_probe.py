"""Malformed / missing provenance probe (dev tooling — NOT part of the submission).

The hidden harness controls the provenance shape, but a robust solution must
degrade gracefully on missing keys, wrong types, or a non-dict provenance — never
crash (a crash scores the item as a no-op) and never mutate on garbage input.

Run:  python3 tests/malformed_provenance_probe.py
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

BODY = "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state."
MUT = ("revise_confidence", "set_scope", "set_status", "add_claim", "add_entity", "add_edge", "drop_claim")

# (name, body, provenance, policy)
#   policy "safe" -> provenance carries no usable strength: must NOT mutate (hold/no_op)
#   policy "any"  -> provenance is messy but has real strength, or body is unusable:
#                    must not crash; a mutation is acceptable (and correct if strong)
CASES = [
    ("M1 empty provenance dict", BODY, {}, "safe"),
    ("M2 provenance is None", BODY, None, "safe"),
    ("M3 missing method_class (but strong)", BODY, {"independent_groups": 4, "replication_count": "many", "effect_strength": "strong", "method_directness": "direct"}, "any"),
    ("M4 wrong types (list / dict / int)", BODY, {"independent_groups": [1, 2, 3], "replication_count": {"x": 1}, "effect_strength": 5, "method_directness": None, "retraction_status": 0}, "safe"),
    ("M5 numeric-in-string count (strong)", BODY, {"independent_groups": "4 groups", "replication_count": "reproduced twice", "effect_strength": "strong", "method_directness": "direct"}, "any"),
    ("M6 negative / absurd values", BODY, {"independent_groups": -3, "replication_count": 9999, "effect_strength": "STRONG", "method_directness": "Direct"}, "any"),
    ("M7 provenance is a bare string", BODY, "strong and replicated", "safe"),
    ("M8 provenance is a list", BODY, ["independent_groups", 4], "safe"),
    ("M9 body is None", None, {"independent_groups": 4, "replication_count": "many", "effect_strength": "strong"}, "any"),
    ("M10 body is non-string", 12345, {"independent_groups": 4}, "any"),
    ("M11 unknown extra keys only", BODY, {"weird_key": "boom", "another": [1]}, "safe"),
]


def main():
    print("=" * 72)
    print("MALFORMED PROVENANCE PROBE  (no crash; no mutation on unusable input)")
    print("=" * 72)
    n = 0
    for name, body, prov, policy in CASES:
        try:
            r = ingest(EvidenceItem("MP", "", body, prov), GraphView(load_seed()))
            ops = [d.op for d in r.deltas]
            well_formed = isinstance(ops, list) and len(ops) > 0
            mutated = any(op in MUT for op in ops)
            guarded = "guarded no-op" in r.rationale       # degraded via exception catch
            if policy == "safe":
                ok = well_formed and not mutated and not guarded
            else:  # "any": just must not crash / not silently die
                ok = well_formed and not guarded
            detail = f"[{policy}] ops={ops} rationale={r.rationale!r}"
        except Exception as exc:
            ok = False
            detail = f"CRASHED: {type(exc).__name__}: {exc}"
        n += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    print("-" * 72)
    print(f"  {n}/{len(CASES)} malformed-input checks pass")
    print("=" * 72)


if __name__ == "__main__":
    main()
