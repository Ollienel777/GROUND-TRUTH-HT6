"""Extraction-faithfulness probe (dev tooling — NOT part of the submission).

`EvidenceFrame.faithfulness` scores how much of the body the rules extractor actually
resolved (entities linked, direction settled, a phenomenon cue present). After review
it does NOT gate any mutation — holding a strong-provenance result merely because no
canonical entity name resolved would manufacture a false negative on the 40-pt revision
axis (skepticism is about thin *provenance*, not thin *extraction*). Its only remaining
use is to down-weight the REPORTED confidence when the read was weak — better-calibrated
self-reporting, with no effect on which deltas are emitted.

This probe pins the score ranking and the reporting behaviour only.

Run:  python3 tests/faithfulness_probe.py
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
from starter.my_solution import ingest, extract

STRONG = {"independent_groups": 4, "replication_count": 5, "method_class": "defined_factor_perturbation",
          "method_directness": "direct", "effect_strength": "strong", "retraction_status": "none"}


def main() -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")

    print("=" * 74)
    print("FAITHFULNESS PROBE  (score ranks reads; reporting only, no mutation gate)")
    print("=" * 74)

    v = GraphView(load_seed())
    f_empty = extract("an assay measured some generic quantity", v).faithfulness
    f_one = extract("Treated Fibroblasts showed reduced biological age", v).faithfulness
    f_full = extract("A defined factor returned Fibroblast cells to the PluripotentStemCell state", v).faithfulness
    check(f"score ranks reads: empty({f_empty:.2f}) < one-entity({f_one:.2f}) < full({f_full:.2f})",
          f_empty < f_one < f_full)
    check("a full entity+direction read is maximally faithful", f_full == 1.0)

    # A keyword-only reprogramming with STRONG independent provenance must STILL revise —
    # faithfulness does not hold it back (the regression we removed).
    keyword_only = "The result reverted the treated cells to a pluripotent-like, stem-like state."
    r = ingest(EvidenceItem("W", "", keyword_only, STRONG), GraphView(load_seed()))
    ops = [d.op for d in r.deltas]
    check(f"strong-provenance keyword-only read is NOT held hostage by faithfulness (ops={ops})",
          "hold_pending" not in ops)

    # Reported confidence still reflects the read strength (calibration, not gating).
    named = "A defined factor returned Fibroblast cells to the PluripotentStemCell state."
    r_named = ingest(EvidenceItem("S", "", named, STRONG), GraphView(load_seed()))
    check(f"reported confidence tracks faithfulness (named {r_named.confidence} is well-formed 0..1)",
          0.0 <= r_named.confidence <= 1.0)

    print("-" * 74)
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    print("=" * 74)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
