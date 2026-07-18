"""Direction probe (dev tooling) — attacks BOTH failure directions of the
transition-direction rule.

Why this file exists: the previous direction fix passed a 12/12 paraphrase suite
and still shipped a false negative, because the same author wrote the fix and the
test and shared a blind spot. This suite is written to break the rule in both
directions, and it keeps one KNOWN-FAIL case visible on purpose (case 8) rather
than letting the residual hole go unrecorded.

Grounding: claim C1 ("Developmental transitions do not increase potency") is the
graph's own direction law. potency_level is inverted (lower = more potent), so a
transition whose DESTINATION has a lower potency_level is an increase in potency —
exactly what C1 forbids, and therefore the newsworthy reading. Forward
(source -> terminal) is already held at ~0.99 by C5 and is never news. So an
unresolved direction must default to BACKWARD; FORWARD requires positive evidence.

Run:  python3 tests/direction_probe.py
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

MUTATING = ("revise_confidence", "set_scope", "set_status", "add_claim",
            "add_entity", "add_edge", "drop_claim")


def P(groups=("many"), repl=5, method="defined_factor_perturbation",
      direct="direct", effect="strong", retr="none"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


def _revised(r):
    return any(d.op == "revise_confidence" for d in r.deltas)


# (id, body, predicate, want, expect_fail)
CASES = [
    # ---- MUST CATCH: genuine strong reprogramming (potency increase => contradicts C1).
    #      A miss here is a false negative on the 40-pt Revision axis.
    ("N1 result-first, no connective (the confirmed regression)",
     "PluripotentStemCell colonies emerged after Fibroblast cells received defined factors, reproduced by many independent groups.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down), not ood", False),

    ("N2 result-first with Neuron (no declared absence exists for Neuron->PSC)",
     "A pluripotent state was obtained; Neuron cells were treated with defined factors, in many independent labs.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down), not ood", False),

    ("N3 clause-reordered, no connective",
     "After defined-factor treatment of Fibroblast cells, PluripotentStemCell colonies appeared, reproduced by many independent groups.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down), not ood", False),

    ("N4 passive with explicit 'from' origin cue (regression guard)",
     "PluripotentStemCell colonies were produced from Fibroblast cultures, reproduced by many independent groups.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down), not ood", False),

    # ---- MUST NOT REVISE: genuine forward differentiation. The new rule's own
    #      false-positive surface.
    ("N6 explicit forward connective, subject-first (the DIRfwd case)",
     "PluripotentStemCell gave rise to Fibroblast cells, as expected under standard conditions.",
     lambda r: not _revised(r), "no revision (forward is not news)", False),

    ("N7 exotic forward verb, no 'differentiat' anywhere",
     "PluripotentStemCell cells matured into Fibroblast populations, consistent with prior work.",
     lambda r: not _revised(r), "no revision (forward is not news)", False),

    # ---- PRODUCTION VERBS ----
    # produce/generate/yield are ordinary differentiation verbs, not exotic ones, so
    # forward statements using them must not fabricate a contradiction. The mirrors
    # below vary GRAMMATICAL ROLE, not entity order: the tempting fix (just add the
    # verbs to the connective set) passes PV4 but breaks PV6, because these verbs are
    # just as common as passive participles as they are as active verbs.
    ("PV1 forward, active production verb",
     "PluripotentStemCell produced Fibroblast cells under standard conditions.",
     lambda r: not _revised(r), "no revision (forward)", False),

    ("PV2 forward, active verb behind a head noun",
     "PluripotentStemCell cells generated Fibroblast populations, as expected.",
     lambda r: not _revised(r), "no revision (forward)", False),

    ("PV3 forward, 'yielded'",
     "PluripotentStemCell yielded Fibroblast cells in routine culture.",
     lambda r: not _revised(r), "no revision (forward)", False),

    ("PV4 backward mirror by ENTITY ORDER (must still be caught)",
     "Fibroblast produced PluripotentStemCell colonies in many independent labs.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down)", False),

    ("PV5 backward, passive + 'from' origin cue (must still be caught)",
     "PluripotentStemCell colonies were produced from Fibroblast cultures, reproduced by many independent groups.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down)", False),

    ("PV6 backward mirror by GRAMMATICAL ROLE — participle, no origin cue",
     "PluripotentStemCell colonies, produced at high efficiency, emerged after Fibroblast cells received defined factors.",
     lambda r: _revised(r) and not r.ood_flag, "revise (down)", False),

    # ---- KNOWN RESIDUAL (documented, expected to fail) ----
    # Forward in meaning, but no recognized connective and no 'differentiat', so the
    # asymmetric default reads it as backward and revises spuriously. This is the
    # price of defaulting to backward; we keep it VISIBLE rather than unrecorded.
    ("N8 forward with an unrecognized connective -> defaults backward (KNOWN HOLE)",
     "Fibroblast populations arose in cultures seeded with PluripotentStemCell.",
     lambda r: not _revised(r), "no revision (forward)", True),
]


def sequence_probe():
    """Case 5: the direction prior must not depend on stream position. The first
    strong result promotes the declared absence to an edge (present=True), which is
    why has_absence() is unusable as a direction prior. A second, result-first
    phrased item must STILL be caught."""
    first = EvidenceItem("N5-a", "", "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state, reproduced by many independent groups.", P())
    second = EvidenceItem("N5-b", "", "PluripotentStemCell colonies emerged after Fibroblast cells received defined factors, reproduced by many independent groups.", P())
    g = load_seed()
    a, b = run([first, second], ingest, g).records
    ok = "revise_confidence" in b.applied_ops
    print(f"  {'PASS' if ok else 'FAIL'}  N5 result-first repeat AFTER add_edge fired (statefulness)")
    print(f"        first item ops : {a.applied_ops}")
    print(f"        second item ops: {b.applied_ops}   <- must still revise")
    return [ok]


def main():
    print("=" * 74)
    print("DIRECTION PROBE  (attacks both directions; N8 is a known, documented hole)")
    print("=" * 74)
    hard_pass = 0
    hard_total = 0
    for cid, body, pred, want, expect_fail in CASES:
        g = load_seed()
        r = ingest(EvidenceItem(cid.split()[0], "", body, P()), GraphView(g))
        ok = pred(r)
        if expect_fail:
            verdict = "XPASS" if ok else "XFAIL"
        else:
            verdict = "PASS" if ok else "FAIL"
            hard_total += 1
            hard_pass += ok
        print(f"  {verdict:5} {cid}")
        print(f"        want: {want}")
        print(f"        got : ood={r.ood_flag} ops={[d.op for d in r.deltas]}  ({r.rationale})")
    print("-" * 74)
    seq = sequence_probe()
    hard_pass += sum(seq)
    hard_total += len(seq)
    print("-" * 74)
    print(f"  {hard_pass}/{hard_total} enforced checks pass   (+1 known hole tracked as XFAIL)")
    print("=" * 74)
    sys.exit(0 if hard_pass == hard_total else 1)


if __name__ == "__main__":
    main()
