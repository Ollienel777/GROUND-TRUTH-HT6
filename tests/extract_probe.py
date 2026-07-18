"""Extract probe (dev tooling) — pins the output of the perception layer.

`extract(body, view)` is the single seam an LLM extractor would replace. This suite
locks the frame it produces on representative bodies, so (a) the eventual LLM version
has an exact behavioral target to match, and (b) a change to the rules extractor is
caught here even if it happens not to flip an end-to-end verdict on the other probes.

Only the fields asserted per case are checked; unlisted fields are ignored, so a case
states just the signals it is about.

Run:  python3 tests/extract_probe.py
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
from starter.my_solution import extract


def frame_of(body):
    return extract(body, GraphView(load_seed()))


# (label, body, {field: expected})  — entity checks use the set of resolved names.
CASES = [
    ("strong defined-factor reprogramming",
     "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state, reproduced by many independent groups.",
     {"names": {"Fibroblast", "PluripotentStemCell"}, "direction": "backward",
      "reaches_source": True, "is_reversion": True, "is_lateral": False, "is_aging": False}),

    ("result-first reprogramming, no connective (direction unresolved)",
     "PluripotentStemCell colonies emerged after Fibroblast cells received defined factors.",
     {"names": {"Fibroblast", "PluripotentStemCell"}, "direction": None,
      "reaches_source": True, "is_reversion": False}),

    ("forward differentiation via connective",
     "PluripotentStemCell gave rise to Fibroblast cells, as expected under standard conditions.",
     {"direction": "forward", "is_reversion": False}),

    ("forward via active production verb",
     "PluripotentStemCell produced Fibroblast cells under standard conditions.",
     {"direction": "forward"}),

    ("lateral transdifferentiation",
     "A factor converted Fibroblast cells directly into Neuron cells, without passing through any intermediate state.",
     {"names": {"Fibroblast", "Neuron"}, "is_lateral": True}),

    ("OOD axis — biological age, identity preserved",
     "Treated Fibroblasts showed reduced biological age and rejuvenated metabolic function while remaining Fibroblasts.",
     {"is_aging": True, "is_function": True, "identity_preserved": True}),

    ("confirmation of a contested claim",
     "A well-powered study demonstrated that differentiated cells retain full nuclear developmental potential.",
     {"is_confirmation": True, "is_reversion": False, "direction": None}),

    ("bare forward wording ('differentiat')",
     "PluripotentStemCell differentiated into MesodermalProgenitor under standard conditions.",
     {"is_forward_worded": True, "direction": "forward"}),

    ("no entities resolvable",
     "Cells did something unspecified in an unspecified way.",
     {"names": set(), "direction": None, "reaches_source": False}),
]


def main():
    print("=" * 70)
    print("EXTRACT PROBE  (pins the perception layer / the LLM's target schema)")
    print("=" * 70)
    npass = 0
    for label, body, want in CASES:
        f = frame_of(body)
        got = {"names": {s.name for s in f.entities}, "direction": f.direction,
               "reaches_source": f.reaches_source, "is_reversion": f.is_reversion,
               "is_forward_worded": f.is_forward_worded, "is_lateral": f.is_lateral,
               "is_aging": f.is_aging, "is_function": f.is_function,
               "identity_preserved": f.identity_preserved, "is_confirmation": f.is_confirmation}
        bad = {k: (want[k], got[k]) for k in want if got[k] != want[k]}
        ok = not bad
        npass += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if bad:
            for k, (exp, act) in bad.items():
                print(f"        {k}: want {exp!r}, got {act!r}")
    print("-" * 70)
    print(f"  {npass}/{len(CASES)} extract checks pass")
    print("=" * 70)
    sys.exit(1 if npass != len(CASES) else 0)


if __name__ == "__main__":
    main()
