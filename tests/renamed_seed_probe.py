"""Renamed-seed harness (dev tooling — NOT part of the submission).

The domain block is byte-identical between the practice and real seeds while the
entity names differ. This runs the 12-item hard stream against a seed whose
ENTITY names are renamed to arbitrary tokens (claim ids / statements / domain
left intact — those are fixed in the real seed, so renaming them would be a false
alarm). Any verdict or trajectory that changes is entity-name coupling we didn't
know we had. Identical results = the classifier is genuinely structural.

Run:  python3 tests/renamed_seed_probe.py
"""
from __future__ import annotations
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from groundtruth.loader import load_seed
from groundtruth.harness import run
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest
from hard_selfcheck import STREAM  # reuse the 12-item stream + expectations

NAME_MAP = {
    "PluripotentStemCell": "Alpha", "MesodermalProgenitor": "Bravo",
    "Fibroblast": "Charlie", "SkeletalMuscleCell": "Delta",
    "Neuron": "Echo", "IntestinalEpithelialCell": "Foxtrot",
}


def rename_body(text):
    for k, v in NAME_MAP.items():
        text = text.replace(k, v)
    return text


def run_variant(rename):
    g = load_seed()
    if rename:
        for cs in g.cell_states.values():
            cs.name = NAME_MAP.get(cs.name, cs.name)
        for a in g.absences.values():
            a.frm = NAME_MAP.get(a.frm, a.frm)
            a.to = NAME_MAP.get(a.to, a.to)
    stream = [EvidenceItem(it.id, "", rename_body(it.body) if rename else it.body, it.provenance, it.era)
              for it, _ in STREAM]
    return run(stream, ingest, g).records


def signature(rec):
    return (rec.attempted_mutation, rec.ood_flag, tuple(sorted(set(rec.applied_ops))),
            tuple(sorted(rec.conf_snapshot.items())))


def main():
    orig = run_variant(rename=False)
    ren = run_variant(rename=True)
    print("=" * 74)
    print("RENAMED-SEED PROBE  (entity names -> arbitrary tokens; verdicts must match)")
    print("=" * 74)
    n = 0
    for (it, _), o, r in zip(STREAM, orig, ren):
        ok = signature(o) == signature(r)
        n += ok
        print(f"  {'MATCH' if ok else 'DIFFER'}  {it.id:4} orig(ood={o.ood_flag}, ops={sorted(set(o.applied_ops))})")
        if not ok:
            print(f"          ren (ood={r.ood_flag}, ops={sorted(set(r.applied_ops))})")
            if o.conf_snapshot != r.conf_snapshot:
                print(f"          conf differs: orig={o.conf_snapshot} ren={r.conf_snapshot}")
    print("-" * 74)
    print(f"  {n}/{len(orig)} items identical under renaming")
    print("=" * 74)
    sys.exit(1 if n != len(orig) else 0)


if __name__ == "__main__":
    main()
