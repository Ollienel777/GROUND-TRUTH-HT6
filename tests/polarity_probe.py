"""Polarity / modality / predication / clause-locality probe (ENFORCED).

These four cases were once known holes (see git history / DESIGN.md): the perception
layer matched classification keywords as flat substrings over the whole body, with no
model of grammatical context. They are now closed by the NegEx/ConText-style scope
guards in the `extract` seam, and this probe ENFORCES that they stay closed (exit 1 on
any failure), the same way direction_probe.py enforces its checks.

  * POLARITY   — a negated keyword ("did NOT revert", "failed to return") must NOT read
                 as an asserted one; a *failed* reprogramming is evidence FOR
                 irreversibility, so it must not revise the irreversibility claim down.
  * MODALITY   — a hypothetical ("IF cells could be driven back ...") is not a reported
                 result and must not mutate state.
  * PREDICATION— a static comparison ("X is MORE POTENT than Y") describes no transition
                 and must not trip the reversion path.
  * CLAUSE-LOCALITY — a distractor state named in a *different* sentence must not enter
                 the structural OOD test and turn a genuine reprogramming into a false
                 lateral-OOD flag.

Run:  python3 tests/polarity_probe.py
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


def P(groups=("many"), repl=5, method="defined_factor_perturbation",
      direct="direct", effect="strong", retr="none"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


def _mutated(r):
    return any(d.op in MUTATING for d in r.deltas)


def _revised(r):
    return any(d.op == "revise_confidence" for d in r.deltas)


# (id, body, provenance, predicate, want, expect_fail)
CASES = [
    # ---- POLARITY: a failed / negated reprogramming supports irreversibility.
    #      It must NOT drive a downward revision of the C3 family.
    ("NEG1 negated reversion ('did not revert / no reprogramming')",
     "Despite defined-factor treatment, Fibroblast cells did not revert to a pluripotent state; no reprogramming was observed.",
     P(),
     lambda r, v: not _mutated(r), "no state change (evidence supports the claim)", False),

    ("NEG2 negated reversion ('failed to return')",
     "Fibroblast cells failed to return to PluripotentStemCell identity under all conditions tested.",
     P(),
     lambda r, v: not _mutated(r), "no state change", False),

    # ---- PREDICATION: a static potency comparison is not a described transition.
    ("CMP1 comparative 'more potent than' (no transition)",
     "PluripotentStemCell is more potent than Fibroblast, as expected under standard models.",
     P(groups="many", method="observational"),
     lambda r, v: not _mutated(r), "no state change (static comparison, not a transition)", False),

    # ---- MODALITY: a hypothetical is not a reported result.
    ("HYP1 hypothetical ('if cells could be driven back ... no such result')",
     "If Fibroblast cells could be driven back to PluripotentStemCell, the field would be transformed; no such result is reported here.",
     P(),
     lambda r, v: not _mutated(r), "no state change (hypothetical, no result)", False),

    # ---- CLAUSE-LOCALITY: a distractor state in another sentence must not turn a
    #      real reprogramming into a false lateral-OOD flag.
    ("MULTI2 distractor same-potency state in a separate clause",
     "Neuron populations were profiled. Separately, Fibroblast cells were reprogrammed "
     "to PluripotentStemCell by defined factors, across many independent groups.",
     P(),
     lambda r, v: _revised(r) and not r.ood_flag, "revise down (reprogramming), NOT ood", False),

    # ---- KNOWN RESIDUAL (tracked XFAIL, like direction_probe.py's N8). The negation
    #      guard anchors on the reversion VOCABULARY; a structural-only negated
    #      reprogramming — a generic change verb ("convert") the reversion lexicon does
    #      not list, negated, with the source/terminal pair driving the default — is not
    #      yet caught. Closing it means applying negation scope to the structural
    #      potency-pair signal, which DESIGN.md warns not to ship without a voice-varying
    #      probe. Left visible rather than silently wrong.
    ("NEG3 structural-only negated reprogramming (verb outside reversion lexicon)",
     "Fibroblast cells did not convert to PluripotentStemCell under any condition tested.",
     P(),
     lambda r, v: not _mutated(r), "no state change (negated); KNOWN residual", True),
]


def main():
    print("=" * 74)
    print("POLARITY / MODALITY / PREDICATION / CLAUSE-LOCALITY PROBE (enforced)")
    print("=" * 74)
    npass = nfail = xfail = xpass = 0
    enforced = [c for c in CASES if not c[5]]
    for cid, body, prov, pred, want, expect_fail in CASES:
        view = GraphView(load_seed())
        r = ingest(EvidenceItem(cid.split()[0], "", body, prov), view)
        ok = pred(r, view)
        if expect_fail:
            verdict = "XPASS" if ok else "XFAIL"
            xpass += ok; xfail += (not ok)
        else:
            verdict = "PASS" if ok else "FAIL"
            npass += ok; nfail += (not ok)
        print(f"  {verdict:5} {cid}")
        print(f"        want: {want}")
        print(f"        got : ood={r.ood_flag} ops={[d.op for d in r.deltas]}  ({r.rationale})")
    print("-" * 74)
    print(f"  {npass}/{len(enforced)} enforced checks pass"
          f"   (+{xfail} known residual tracked as XFAIL)")
    if xpass:
        print("  NOTE: an XPASS means a guard now closes a residual — promote it to enforced.")
    print("=" * 74)
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
