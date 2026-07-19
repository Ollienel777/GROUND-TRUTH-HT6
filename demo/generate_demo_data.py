"""Regenerate the numbers the demo visualizes, straight from the real solution.

The animated page (`belief_revision_demo.html`) embeds a *snapshot* of these values
so it can run standalone. Run this whenever the model changes to see the true, current
trajectory and refresh the snapshot by hand.

    python demo/generate_demo_data.py            # pretty table to stdout
    python demo/generate_demo_data.py --json     # machine-readable dump -> demo/demo_data.json

It drives the same 12-item hard stream used by tests/hard_selfcheck.py through the real
`ingest` and the real Delta API, and records, per item: the emitted ops, the ood flag,
and the confidence snapshot of every tracked claim. Nothing here is hand-authored —
it is exactly what the harness produces.
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groundtruth.loader import load_seed
from groundtruth.harness import run
from starter.my_solution import ingest
from tests.hard_selfcheck import STREAM, TRACK


def collect():
    g = load_seed()
    init = {c: round(g.claims[c].confidence, 4) for c in TRACK if c in g.claims}
    log = run([it for it, _ in STREAM], ingest, g)
    rows = []
    for (item, exp), rec in zip(STREAM, log.records):
        rows.append({
            "id": item.id,
            "body": item.body,
            "provenance": item.provenance,
            "expectation": exp,
            "applied_ops": rec.applied_ops,
            "ood_flag": rec.ood_flag,
            "confidence": rec.conf_snapshot,
        })
    return {"initial": init, "tracked_claims": TRACK, "items": rows,
            "structural_violations": log.structural_violations}


def main():
    data = collect()
    if "--json" in sys.argv:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"wrote {out}")
        return
    print("initial:", data["initial"])
    print(f"firewall violations: {data['structural_violations'] or 'none'}")
    print("-" * 78)
    print(f"{'item':4} {'ops':45} {'ood':6} C3c  C3g  C4")
    for r in data["items"]:
        s = r["confidence"]
        print(f"{r['id']:4} {','.join(r['applied_ops'])[:44]:45} "
              f"{str(r['ood_flag']):6} {s.get('C3c',0):.2f} {s.get('C3g',0):.2f} {s.get('C4',0):.2f}")


if __name__ == "__main__":
    main()
