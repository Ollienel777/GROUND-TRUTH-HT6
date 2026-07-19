"""Pending-overlap probe (dev tooling — NOT part of the submission).

`_match_pending` resolves which held (pending) claim an incoming retraction /
failed-replication refers to, by subject overlap with the states named in the item.
The old rule returned the FIRST pending sharing any state; with several outstanding
pendings that could drop the WRONG one. The fix picks the pending with the MOST
subject overlap. This probe sets up multiple simultaneous pendings and checks the
right one is selected — and that a non-overlapping subject still resolves nothing
(never a blind guess).

Run:  python3 tests/pending_overlap_probe.py
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
from starter.my_solution import _match_pending, _pending_id


def states_for(view, names):
    return [view.cell_state(n) for n in names]


def main() -> bool:
    g = load_seed()
    view = GraphView(g)
    ok = True

    # Two outstanding pendings. Note the ORDER: the broad one is inserted first, so a
    # first-match rule would return it for a Neuron-only item even though the second
    # pending is the exact subject.
    p_broad = _pending_id(states_for(view, ["Fibroblast", "IntestinalEpithelialCell"]))
    p_neuron = _pending_id(states_for(view, ["Neuron"]))
    g.pending[p_broad] = {"note": "broad", "evidence_id": "e0"}
    g.pending[p_neuron] = {"note": "neuron", "evidence_id": "e1"}

    print("=" * 72)
    print("PENDING-OVERLAP PROBE  (most-overlap wins; no blind guess)")
    print("=" * 72)

    cases = [
        ("Neuron-only retraction -> the Neuron pending",       ["Neuron"], p_neuron),
        ("Fibroblast retraction -> the broad pending",         ["Fibroblast"], p_broad),
        ("both broad subjects -> the broad pending",           ["Fibroblast", "IntestinalEpithelialCell"], p_broad),
        ("unrelated subject (SkeletalMuscleCell) -> no match", ["SkeletalMuscleCell"], None),
    ]
    for label, names, want in cases:
        got = _match_pending(GraphView(g), states_for(view, names))
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label:<48} got={got}")

    # No states named at all, and >1 pending outstanding -> ambiguous -> no match.
    amb = _match_pending(GraphView(g), [])
    good = amb is None
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'}  no subject named, 2 pendings -> ambiguous     got={amb}")

    print("-" * 72)
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    print("=" * 72)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
