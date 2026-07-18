"""Negation / modality / predication / clause-locality probe (dev tooling).

The extractor's keyword sets (_REVERSION_KW, _SOURCE_KW, _LATERAL_KW) are flat
substring matches over the whole body, with no model of four things a sentence can
do to a matched cue:

  * POLARITY      — "did NOT revert", "NO reprogramming was observed"      (NEG1, NEG2)
  * MODALITY      — "IF cells COULD be driven back ... no such result"     (HYP1)
  * PREDICATION   — "IS more potent THAN" is a static comparison, not an event (CMP1)
  * CLAUSE LOCALITY — a distractor state in ANOTHER sentence poisons the OOD
                      lateral test, dropping the real contradiction          (MULTI2)

Each of the four below is a demonstrated failure of the pre-guard extractor: it
either revised a belief in the WRONG direction (a failed / hypothetical / static
statement read as a reprogramming event) or mis-routed a real in-model
contradiction to OOD because of a distractor in a different clause. The three
controls confirm the guards do not over-fire: an ordinary forward chain and an
oblique-worded reprogramming keep their prior verdicts.

Grounding: potency_level is inverted (lower = more potent). A "reversion" is a move
toward lower potency_level, which C1 forbids and is therefore the newsworthy
reading — but ONLY if such an event is actually asserted. A negated, hypothetical,
or merely comparative sentence asserts no event, so the correct move is no revision.

Run:  python3 tests/negation_probe.py
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

MUTATING = ("revise_confidence", "set_scope", "set_status", "add_claim",
            "add_entity", "add_edge", "drop_claim")


def P(groups=4, repl=5, method="defined_factor_perturbation",
      direct="direct", effect="strong", retr="none"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


def _revised(r):
    return any(d.op == "revise_confidence" for d in r.deltas)


# (id, body, provenance, predicate, want)
CASES = [
    # ---- POLARITY: a failed / null result is EVIDENCE FOR irreversibility, never
    #      against it. Reading the reversion keyword regardless of polarity revised
    #      C3c DOWN — exactly backwards, on the 40-pt axis. ----
    ("NEG1 explicit negation of reversion (strong prov)",
     "Fibroblast cells did not revert to a pluripotent state; no reprogramming was observed.",
     P(4, 5),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (a failed reprogramming attempt is not a contradiction)"),

    ("NEG2 negated return, second null clause (strong prov)",
     "Despite defined-factor treatment, Fibroblast cells failed to return to the "
     "PluripotentStemCell state; no dedifferentiation was detected.",
     P(4, 5),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (null result)"),

    # ---- PREDICATION: a static comparison ("is more potent than") describes no
    #      transition. The bare "more potent" cue drove a large, confident revision
    #      of a near-certain claim off a sentence with no event. ----
    ("CMP1 comparative, not a transition (strong observational)",
     "PluripotentStemCell is more potent than Fibroblast, as expected.",
     P("several", "several", "observational"),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (static comparison, no event)"),

    # ---- CLAUSE LOCALITY: a distractor same-potency state in a DIFFERENT sentence
    #      satisfied the lateral-OOD test and dropped the real contradiction. The
    #      real event (Fibroblast -> PSC) is an in-model reprogramming. ----
    ("MULTI2 distractor state in another clause -> must be in-model, not OOD",
     "Neuron populations were profiled. Separately, Fibroblast cells were "
     "reprogrammed to PluripotentStemCell by defined factors.",
     P(4, 5),
     lambda r: _revised(r) and not r.ood_flag,
     "revise (down) in-model; the Neuron distractor must not trigger lateral OOD"),

    # ---- MODALITY: a conditional / hypothetical describes no experiment. ----
    ("HYP1 hypothetical, explicitly unrealized (strong prov attached to a non-result)",
     "If Fibroblast cells could be driven back to PluripotentStemCell, it would "
     "overturn the dogma; no such result is reported.",
     P(4, 5),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (hypothetical, no experiment happened)"),

    # ---- CONTROLS: the guards must not over-fire. ----
    ("CTRL1 ordinary forward chain -> no_op (unchanged)",
     "Under standard conditions, PluripotentStemCell differentiated into "
     "MesodermalProgenitor and then into Fibroblast.",
     P("many", "many", "observational"),
     lambda r: not _revised(r) and not r.ood_flag,
     "no_op (forward differentiation is not news)"),

    ("CTRL2 forward via 'seeded with' + differentiation cue -> no_op (unchanged)",
     "Fibroblast populations arose in dishes seeded with PluripotentStemCell during differentiation.",
     P("many", "many", "observational"),
     lambda r: not _revised(r) and not r.ood_flag,
     "no_op (forward)"),

    ("CTRL3 genuine reprogramming, oblique wording -> revise down (unchanged)",
     "Cells reverted to the most primitive pluripotent state, reproduced by many independent groups.",
     P("many", 5),
     lambda r: _revised(r) and not r.ood_flag,
     "revise (down) in-model"),

    # ---- GENERALIZATION: the guards must fire on paraphrases, and must NOT
    #      over-fire on true positives that merely contain a negation/comparison
    #      token. These are the false-positive traps the fix must survive. ----
    ("GEN1 negation paraphrase ('never restored')",
     "Fibroblast cells were never restored to the PluripotentStemCell state despite defined factors.",
     P(4, 5),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (negated)"),

    ("GEN2 inverted-conditional hypothetical ('Were X to revert ...')",
     "Were Fibroblast cells to revert to PluripotentStemCell, the dogma would fall; this remains hypothetical.",
     P(4, 5),
     lambda r: not _revised(r) and not r.ood_flag,
     "no revision (subject-aux inversion + 'hypothetical')"),

    ("GEN3 FALSE-POSITIVE GUARD: 'no longer holds' is a reprogramming assertion, not a negation",
     "Fibroblast can be driven to the PluripotentStemCell state; the irreversibility no longer holds, "
     "confirmed by many independent groups.",
     P("many", 5),
     lambda r: _revised(r) and not r.ood_flag,
     "revise (down) — 'no longer' must NOT suppress the event"),

    ("GEN4 FALSE-POSITIVE GUARD: 'became more potent' is a change verb, not a static comparison",
     "Fibroblast cells became more potent, acquiring a pluripotent-like state, across many independent groups.",
     P("many", 5),
     lambda r: _revised(r) and not r.ood_flag,
     "revise (down) — change verb, not 'is ... than'"),
]


def main():
    print("=" * 76)
    print("NEGATION PROBE  (polarity / modality / predication / clause-locality)")
    print("=" * 76)
    npass = 0
    for cid, body, prov, pred, want in CASES:
        g = load_seed()
        r = ingest(EvidenceItem(cid.split()[0], "", body, prov), GraphView(g))
        ok = pred(r)
        npass += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {cid}")
        print(f"        want: {want}")
        print(f"        got : ood={r.ood_flag} ops={[d.op for d in r.deltas]}  ({r.rationale})")
    print("-" * 76)
    print(f"  {npass}/{len(CASES)} guard checks pass")
    print("=" * 76)
    sys.exit(0 if npass == len(CASES) else 1)


if __name__ == "__main__":
    main()
