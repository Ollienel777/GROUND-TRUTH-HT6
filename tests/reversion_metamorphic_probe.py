"""Reversion must-flip probe (dev tooling — NOT part of the submission).

The metamorphic sibling of metamorphic_probe.py, on the REVISION axis (40 pts). The
correctness spine from the original review: a metamorphic relation is per-transform,
NOT a blanket invariance. Two opposite relations here:

  * INVARIANT  (meaning-preserving: synonym, voice, clause reorder) -> the verdict
    MUST HOLD. An asserted reversion still drives a revision. This is the RECALL
    direction; reds are a residual (measured), and here they're structurally
    backstopped by potency so they hold even for verbs outside the lexicon.

  * MUST-FLIP  (meaning-CHANGING: negation, modality, static comparison, hedge) ->
    the verdict MUST CHANGE. The reversion is not an asserted event, so it must NOT
    revise. This is the PRECISION direction on the 40-pt axis: a missed flip is a
    false-positive revision (an unwarranted belief change). The confirmed cases GATE
    (a regression here is a real bug); genuine gaps are tracked XFAIL, not gated and
    not silently patched.

polarity_probe.py already enforces the explicit-negation / hypothetical / comparison
guards as hand-written cases; this probe re-frames them metamorphically (one base,
many transforms) and adds transforms polarity_probe never tested — externally-sourced
paraphrases and, critically, EPISTEMIC MODALITY / HEDGE, which surfaced two gaps.

Run:  python3 tests/reversion_metamorphic_probe.py   (exit 0 unless a GATED case regresses)
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


def P():
    # Strong, independently-replicated provenance: nothing about the PROVENANCE should
    # suppress the base revision, so a suppressed verdict can only come from the BODY
    # classification (assertion status) — which is exactly what must-flip transforms change.
    return {"replication_count": 5, "independent_groups": "many",
            "method_class": "defined_factor_perturbation", "method_directness": "direct",
            "effect_strength": "strong", "retraction_status": "none"}


def _revises(body: str) -> bool:
    r = ingest(EvidenceItem("R", "", body, P()), GraphView(load_seed()))
    return any(d.op == "revise_confidence" for d in r.deltas)


BASE = "Across many independent groups, defined factors reverted Fibroblast cells to the PluripotentStemCell state."

# INVARIANT: meaning preserved -> MUST still revise (recall; potency-backstopped).
GATE_INVARIANT = [
    ("passive voice", "Across many independent groups, Fibroblast cells were reverted to the PluripotentStemCell state by defined factors."),
    ("clause reorder", "Fibroblast cells were reverted to the PluripotentStemCell state, across many independent groups, by defined factors."),
    ("synonym 'reset' OUTSIDE _REV_VERBS (structural backstop)", "Across many independent groups, defined factors reset Fibroblast cells to the PluripotentStemCell state."),
    ("synonym 'coaxed ... back'", "Across many independent groups, defined factors coaxed Fibroblast cells back to the PluripotentStemCell state."),
]

# MUST-FLIP, CONFIRMED: meaning changed -> MUST NOT revise. These pass today (polarity
# guards); gated so a future edit that reopens them fails here.
GATE_FLIP = [
    ("explicit negation 'did not revert'", "Across many independent groups, defined factors did not revert Fibroblast cells to the PluripotentStemCell state."),
    ("negation paraphrase 'never restored'", "Across many independent groups, Fibroblast cells were never restored to the PluripotentStemCell state."),
    ("hypothetical 'if ... could'", "If defined factors could revert Fibroblast cells to the PluripotentStemCell state, dogma would fall; no such result here."),
    ("static comparison 'more potent than'", "Across many independent groups, the PluripotentStemCell state is more potent than Fibroblast."),
]

# MUST-FLIP, GAPS (tracked XFAIL — currently STILL revise, want no revision):
#   (1) negation-verb coverage: "did not reach" — same class as NEG3 ("did not convert")
#       but "reach" is outside the structural-negation transition-verb list, so the
#       potency default reads it as a reversion. Likely a real false-positive.
#   (2) epistemic modality / hedge: "may / appears to / suggests ... might" are not in
#       _HYP_RE (which only catches conditionals). ARCHITECTURAL judgment call: is this
#       magnitude (correctly provenance-driven, ignore body) or assertion-status
#       (legitimately classified, like 'if')? Flagged, not patched, pending decision.
XFAIL_FLIP = [
    ("negation-verb gap: 'did not reach' (cf. NEG3 'did not convert')", "Across many independent groups, Fibroblast cells remained committed and did not reach the PluripotentStemCell state."),
    ("epistemic modal 'may revert'", "Across many independent groups, defined factors may revert Fibroblast cells to the PluripotentStemCell state."),
    ("epistemic modal 'appear to revert'", "Across many independent groups, defined factors appear to revert Fibroblast cells to the PluripotentStemCell state."),
    ("hedge 'results suggest ... might revert'", "These results suggest Fibroblast cells might revert to the PluripotentStemCell state, across many independent groups."),
]


def main():
    print("=" * 78)
    print("REVERSION MUST-FLIP PROBE  (revision axis, 40 pts)")
    print("=" * 78)
    print(f"  BASE revises: {_revises(BASE)}   (must be True for the row to be meaningful)")
    gated_fail = []

    print("\n  INVARIANT (meaning preserved -> MUST still revise):")
    for label, body in GATE_INVARIANT:
        ok = _revises(body)
        if not ok:
            gated_fail.append(label)
        print(f"    {'ok  ' if ok else 'FAIL'}  revise={ok!s:5}  {label}")

    print("\n  MUST-FLIP, confirmed (meaning changed -> MUST NOT revise):")
    for label, body in GATE_FLIP:
        flipped = not _revises(body)
        if not flipped:
            gated_fail.append(label)
        print(f"    {'ok  ' if flipped else 'FAIL'}  revise={(not flipped)!s:5}  {label}")

    print("\n  MUST-FLIP, tracked gaps (XFAIL — currently still revise):")
    for label, body in XFAIL_FLIP:
        still = _revises(body)
        tag = "XFAIL" if still else "XPASS(closed?)"
        print(f"    {tag:14} revise={still!s:5}  {label}")

    print("\n" + "=" * 78)
    if gated_fail:
        print(f"  GATE FAILED: {len(gated_fail)} gated case(s) regressed: {gated_fail}")
    else:
        print("  GATE OK: recall holds, confirmed must-flip guards hold; 2 gap families tracked XFAIL.")
    print("=" * 78)
    sys.exit(1 if gated_fail else 0)


if __name__ == "__main__":
    main()
