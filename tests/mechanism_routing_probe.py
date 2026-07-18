"""Mechanism-routing probe (dev tooling — NOT part of the submission).

The scoped-revision machinery is the most structurally intricate part of the
solution and, until now, only two of its four branches were exercised anywhere
(hard_selfcheck covers defined_factor -> C3c and env_stress -> C3d; the
spontaneous -> C3a and oocyte_nt -> C3b branches were entirely untested). This
suite pins the whole scoped-revision contract on the REAL seed:

  1. ROUTING     — each provenance.method_class revises the RIGHT child claim
                   (C3a/C3b/C3c/C3d) and leaves the other three siblings untouched.
  2. SCOPE       — the revised child is narrowed with the matching `refuted_under`
                   mechanism tag (narrow, don't delete).
  3. UMBRELLA    — C3g ("cannot return by ANY mechanism") tracks the WEAKEST link:
                   after one child drops, C3g == min(children), never below.
  4. COMPLEMENT  — strong reversion evidence RAISES the contested C4 ("differentiated
                   cells retain full nuclear developmental potential"), never lowers it.
  5. ADD_EDGE    — a declared absence (Fibroblast->PSC) is promoted to a real edge
                   carrying the mechanism as `via`; a pair with NO declared absence
                   (Neuron->PSC) is revised but MUST NOT fabricate an edge.

All expectations were read off the current model and are the correct behavior;
a FAIL means the scoped-revision contract regressed.

Run:  python3 tests/mechanism_routing_probe.py
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
from groundtruth.harness import run
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest

CHILDREN = ["C3a", "C3b", "C3c", "C3d"]


def P(groups, repl, method, direct="direct", effect="strong", retr="none"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


# (label, body, method_class, expected_child, expected_scope_tag)
ROUTING = [
    ("spontaneous -> C3a",
     "Fibroblast cells spontaneously returned to the PluripotentStemCell state, reproduced by many independent groups.",
     "spontaneous", "C3a", "spontaneous"),
    ("oocyte nuclear transfer -> C3b",
     "Via oocyte nuclear transfer, Fibroblast nuclei returned to the PluripotentStemCell state, reproduced by many independent groups.",
     "oocyte_nuclear_transfer", "C3b", "oocyte_nt"),
    ("defined-factor -> C3c",
     "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state, reproduced by many independent groups.",
     "defined_factor_perturbation", "C3c", "defined_factor"),
    ("environmental stress -> C3d",
     "An environmental-stress protocol returned Fibroblast cells to the PluripotentStemCell state, reproduced by many independent groups.",
     "environmental_stress", "C3d", "env_stress"),
]


def _run_one(body, method):
    g = load_seed()
    before = {c: g.claims[c].confidence for c in CHILDREN + ["C3g", "C4"]}
    item = EvidenceItem("MR", "", body, P("many", 5, method))
    rec = run([item], ingest, g).records[0]
    after = {c: g.claims[c].confidence for c in CHILDREN + ["C3g", "C4"]}
    # re-ingest against a fresh view to inspect the emitted delta payloads
    payloads = ingest(EvidenceItem("MR", "", body, P("many", 5, method)),
                      GraphView(load_seed())).deltas
    return before, after, rec, payloads


def main():
    print("=" * 76)
    print("MECHANISM-ROUTING PROBE  (scoped revision: routing/scope/umbrella/edge/C4)")
    print("=" * 76)
    npass = 0
    ntot = 0

    for label, body, method, child, tag in ROUTING:
        before, after, rec, payloads = _run_one(body, method)

        # 1. ROUTING: target child dropped, the other three siblings unchanged
        siblings = [c for c in CHILDREN if c != child]
        routed = after[child] < before[child] - 0.05
        siblings_flat = all(abs(after[c] - before[c]) < 1e-9 for c in siblings)

        # 2. SCOPE: matching refuted_under tag set on the child
        scope_ok = any(d.op == "set_scope" and d.payload.get("claim_id") == child
                       and d.payload.get("scope", {}).get("refuted_under") == tag
                       for d in payloads)

        # 3. UMBRELLA: C3g == min(children) (weakest link), and it moved down
        umbrella_ok = abs(after["C3g"] - min(after[c] for c in CHILDREN)) < 1e-6 and after["C3g"] < before["C3g"]

        # 4. COMPLEMENT: C4 raised, never lowered
        complement_ok = after["C4"] > before["C4"]

        # 5. ADD_EDGE: Fibroblast->PSC absence promoted, carrying the mechanism as via
        edge_ok = any(d.op == "add_edge" and d.payload.get("from") == "Fibroblast"
                      and d.payload.get("to") == "PluripotentStemCell"
                      and d.payload.get("via") == tag for d in payloads)

        for name, ok, detail in [
            (f"{label}: routes to {child}, siblings untouched", routed and siblings_flat,
             f"{child}:{before[child]:.3f}->{after[child]:.3f} siblings_flat={siblings_flat}"),
            (f"{label}: scope refuted_under={tag}", scope_ok, ""),
            (f"{label}: C3g == min(children)", umbrella_ok, f"C3g:{before['C3g']:.3f}->{after['C3g']:.3f}"),
            (f"{label}: C4 strengthened", complement_ok, f"C4:{before['C4']:.3f}->{after['C4']:.3f}"),
            (f"{label}: add_edge via={tag}", edge_ok, ""),
        ]:
            ntot += 1
            npass += ok
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            if detail:
                print(f"        {detail}")

    # NEGATIVE add_edge: Neuron->PSC has no declared absence -> revise but no edge
    g = load_seed()
    body = "A defined-factor method returned Neuron cells to the PluripotentStemCell state, reproduced by many independent groups."
    r = ingest(EvidenceItem("MR-N", "", body, P("many", 5, "defined_factor_perturbation")), GraphView(g))
    ops = [d.op for d in r.deltas]
    neg_ok = ("revise_confidence" in ops) and ("add_edge" not in ops) and not r.ood_flag
    ntot += 1
    npass += neg_ok
    print(f"  {'PASS' if neg_ok else 'FAIL'}  Neuron->PSC (no declared absence): revises but no add_edge")
    print(f"        ops={ops}")

    print("-" * 76)
    print(f"  {npass}/{ntot} scoped-revision checks pass")
    print("=" * 76)
    sys.exit(0 if npass == ntot else 1)


if __name__ == "__main__":
    main()
