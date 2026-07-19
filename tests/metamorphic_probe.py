"""Metamorphic extraction probe (dev tooling — NOT part of the submission).

Extraction robustness on HIDDEN WORDING. The hidden set will phrase the same
phenomenon in words we never saw. We cannot enumerate those words; we can only
(a) push each extraction decision onto STRUCTURE where possible, and (b) MEASURE
what remains lexical with an *externally sourced* synonym pool — synonyms picked
from domain vocabulary that deliberately sit OUTSIDE our detector's keyword lists.
If the test's synonyms came from the same list the detector keys on, green would
mean nothing.

Per-row metamorphic RELATION (the correctness spine — a blanket "verdict must not
change" is WRONG for polarity/modality rows built later):
  * INVARIANT transforms preserve meaning  -> verdict MUST hold
  * MUST-FLIP transforms change meaning     -> verdict MUST change

Two OOD rows here, with OPPOSITE jobs — only one is a guardrail:

  ROW 1  OOD-PHENOMENON RECALL  (relation INVARIANT: OOD flag must survive
         re-wording).  MEASUREMENT ONLY, never gates: its reds are an ACCEPTED
         lexical residual. Acting on them = broadening keyword lists = the
         negative-EV arms race on a precision-weighted axis. Reds stay red.

  ROW 2  OOD near-miss PRECISION  (relation INVARIANT: an in-model item stays
         in-model under re-wording).  This CAN gate, because "don't false-flag a
         modeled transition" is a legitimate must-hold on the 35-pt precision
         axis. What it actually locks is the STRUCTURAL `in_model_transition`
         guard — NOT keyword discipline. Verified: broadening _AGE_KW/_LATERAL_KW
         does NOT clip the reaches-source near-miss (the guard is upstream of the
         keyword check), so this gate is a tripwire for a WEAKENED GUARD, not for
         keyword-broadening. Bounded, not a proof of global precision: it catches
         the sampled near-miss regression, nothing more.

Row 2 gates only items that are UNAMBIGUOUSLY in-model (reach the source state or
change potency). A genuine structural precision hole found while building this —
a contrast clause ("unlike Neuron cells") that trips the lateral detector — is
tracked as XFAIL, not gated and not silently fixed.

Run:  python3 tests/metamorphic_probe.py    (exit 0 unless a GATED near-miss regresses)
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

# Keyword lists imported ONLY to annotate pool phrases as novel vs known (proof
# the pool is external). Detector behavior is read from ingest(), never predicted.
try:
    from starter.my_solution import _AGE_KW, _FUNC_KW, _LATERAL_KW
    _KW = {"age": _AGE_KW, "func": _FUNC_KW, "lateral": _LATERAL_KW}
except Exception:                                             # pragma: no cover
    _KW = {}


def P(groups="several", repl="several", method="observational", effect="moderate"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": "direct", "effect_strength": effect, "retraction_status": "none"}


def _verdict(body: str):
    g = load_seed()
    r = ingest(EvidenceItem("M", "", body, P()), GraphView(g))
    ops = {d.op: d.payload for d in r.deltas}
    op = next((o for o in ("propose_axis", "propose_regime") if o in ops), None)
    name = ""
    if op:
        name = ops[op].get("axis") or ops[op].get("regime") or ""
    return bool(r.ood_flag), op, name


# ---------------------------------------------------------------------------
# ROW 1 — OOD-phenomenon RECALL (measurement, non-gating)
# ---------------------------------------------------------------------------
# {PHEN} is where the phenomenon wording goes; the rest sets the STRUCTURE
# available (states named, identity clause). Relation = INVARIANT (flag must hold).
BASES = [
    ("age  + identity clause     (one state, 'while remaining')",
     "Treated Fibroblasts {PHEN} while remaining Fibroblasts. Reproducible.",
     "age", ("axis", "age")),
    ("age  + NO identity clause  (one state, bare)  <- pure keyword path",
     "Fibroblasts {PHEN}. Reproducible.",
     "age", ("axis", "age")),
    ("func + identity clause     (one state, 'cell type unchanged')",
     "Fibroblasts {PHEN} while their cell type was unchanged. Reproducible.",
     "func", ("axis", "function")),
    ("lateral (both terminals named in one clause)  <- structural path",
     "A single factor {PHEN}. Reproducible.",
     "lateral", ("regime", "lateral")),
]

# Externally-sourced pools: 1-2 KNOWN controls (contain a keyword) then NOVEL
# domain phrasings chosen to avoid every keyword substring. A flagged NOVEL phrase
# means STRUCTURE (not the keyword) caught it.
POOLS = {
    "age": [
        "showed reduced biological age",            # control
        "were rejuvenated",                         # control
        "had their epigenetic clock reset",         # novel
        "showed markedly lengthened telomeres",     # novel
        "exhibited a strong geroprotective response",  # novel
        "reversed their methylation age",           # novel
        "showed restored mitochondrial vigor",      # novel
    ],
    "func": [
        "increased their contractile function",     # control
        "improved metabolic output",                # control
        "cleared pathogens far more effectively",   # novel
        "conducted action potentials faster",       # novel
        "healed wounds more quickly",               # novel
        "pumped calcium more strongly",             # novel
    ],
    "lateral": [
        "converted Fibroblast directly into Neuron",   # control
        "transdifferentiated Fibroblast to Neuron",    # control
        "converted Fibroblast into Neuron",            # novel (verb only)
        "switched Fibroblast to a Neuron fate",        # novel
        "turned Fibroblast into a Neuron",             # novel
        "reprogrammed Fibroblast to become Neuron",    # novel
    ],
}


def _novel(phrase: str, pool_key: str) -> bool:
    kws = _KW.get(pool_key, ())
    low = phrase.lower()
    return not any(k in low for k in kws)


def _row1_recall():
    print("ROW 1 :: OOD-PHENOMENON RECALL :: relation = INVARIANT (flag must hold)")
    print("  MEASUREMENT ONLY — reds are an accepted lexical residual, NEVER gated.")
    total_flag = total_n = 0
    for label, template, pool_key, want in BASES:
        kind_want, name_want = want
        phrases = POOLS[pool_key]
        flag_hits = subtype_hits = 0
        rows = []
        for ph in phrases:
            ood, op, name = _verdict(template.format(PHEN=ph))
            novel = _novel(ph, pool_key)
            how = "MISS" if not ood else ("backstop" if novel else "keyword")
            subtype_ok = ood and op == ("propose_%s" % kind_want) and name_want in name
            flag_hits += ood
            subtype_hits += subtype_ok
            rows.append((novel, ph, ood, op, name, how, subtype_ok))
        n = len(phrases)
        total_flag += flag_hits
        total_n += n
        print(f"\n  [{label}]   want propose_{kind_want}(...{name_want}...)")
        for novel, ph, ood, op, name, how, subtype_ok in rows:
            tag = "novel*" if novel else "known "
            got = f"{op}({name})" if op else "(no OOD delta)"
            st = "st:ok " if subtype_ok else "st:adj" if ood else "      "
            print(f"      {tag} flag={'Y' if ood else 'N'} {how:8} {st}  {got:34} \"{ph}\"")
        # 'residual' keeps the battery tally-backup from reading m<n here as a fail.
        print(f"    -> flag recall {flag_hits}/{n}, sub-type {subtype_hits}/{n}  (residual expected)")
    print(f"\n  ROW 1 overall flag recall on re-worded phenomena: {total_flag}/{total_n}  (residual, not a failure)")


# ---------------------------------------------------------------------------
# ROW 2 — OOD near-miss PRECISION (gates the structural guard)
# ---------------------------------------------------------------------------
# GATED: unambiguously in-model (reaches source OR changes potency). Relation =
# INVARIANT, want ood=False. Re-worded exotic vocab must NOT flip them to OOD.
# Regression here = the in_model_transition guard was weakened/reordered.
PRECISION_GATE = [
    ("rejuvenation -> source        (AGE_KW present, reaches source)",
     "Fibroblast cells were rejuvenated to a PluripotentStemCell state. Reproducible."),
    ("de-aged -> source             (NOVEL aging word, reaches source)",
     "Fibroblast cells were de-aged to a PluripotentStemCell state. Reproducible."),
    ("restored to youthful -> source",
     "Fibroblast cells were restored to a youthful PluripotentStemCell state. Reproducible."),
    ("aged ... converted back -> source",
     "Aged Fibroblast cells were converted back to the PluripotentStemCell state. Reproducible."),
    ("forward potency change        (PSC -> Mesoderm)",
     "PluripotentStemCell cells differentiated into MesodermalProgenitor cells. Reproducible."),
    ("dedifferentiation to less-committed state",
     "Fibroblast cells dedifferentiated to a MesodermalProgenitor state. Reproducible."),
    ("reprogramming + FUNC_KW 'function' -> source",
     "Fibroblasts were reprogrammed to PluripotentStemCell, restoring pluripotent function. Reproducible."),
    # Co-mention contrast (was XFAIL): a distractor terminal named in a contrast aside
    # must NOT be mis-paired with the real subject. Fixed by _strip_contrast; now gated.
    ("contrast 'unlike Neuron cells' (subject Fib -> PSC)",
     "Fibroblast cells, unlike Neuron cells, were reprogrammed to a PluripotentStemCell state. Reproducible."),
    ("comparison 'compared with Neuron cells' (subject Fib -> PSC)",
     "Compared with Neuron cells, Fibroblast cells reverted to the PluripotentStemCell state. Reproducible."),
]

# Genuine laterals wrapped AROUND a contrast aside. These are the false-negative risk
# a naive contrast-split would introduce (subject severed from its conversion target);
# _strip_contrast excises only the aside and leaves the main clause intact, so they MUST
# still fire. Written as gated cases, NOT waved off as "contrived" (condition 2).
LATERAL_ASIDE_GATE = [
    ("straddling aside, no state ('unlike its usual fate')",
     "A single factor turned Fibroblast, unlike its usual fate, into Neuron. Reproducible."),
    ("parenthetical distractor state ('unlike IntestinalEpithelialCell')",
     "A single factor converted Fibroblast, unlike IntestinalEpithelialCell cells, into Neuron. Reproducible."),
]

def _row2_precision():
    print("\n" + "-" * 78)
    print("ROW 2 :: OOD NEAR-MISS PRECISION :: relation = INVARIANT (stay in-model)")
    print("  GATES the structural in_model_transition guard + contrast-aside handling.")
    gated_fail = []

    print("  (a) in-model must NOT flag  (want ood=False):")
    a_fail = 0
    for label, body in PRECISION_GATE:
        ood, op, name = _verdict(body)
        ok = not ood
        a_fail += not ok
        if not ok:
            gated_fail.append(label)
        print(f"    {'ok  ' if ok else 'FAIL'}  {label:52} -> {(op and f'{op}({name})') or 'in-model'}")
    n = len(PRECISION_GATE)
    print(f"    -> {n - a_fail}/{n} hold in-model")

    print("  (b) genuine lateral AROUND a contrast aside must STILL flag  (want ood=True lateral):")
    b_fail = 0
    for label, body in LATERAL_ASIDE_GATE:
        ood, op, name = _verdict(body)
        ok = ood and op == "propose_regime" and "lateral" in name
        b_fail += not ok
        if not ok:
            gated_fail.append(label)
        print(f"    {'ok  ' if ok else 'FAIL'}  {label:52} -> {(op and f'{op}({name})') or 'in-model'}")
    m = len(LATERAL_ASIDE_GATE)
    print(f"    -> {m - b_fail}/{m} genuine laterals preserved")
    return gated_fail


def main():
    print("=" * 78)
    print("METAMORPHIC PROBE  (extraction robustness on hidden wording)")
    print("=" * 78)
    _row1_recall()
    gated_fail = _row2_precision()
    print("\n" + "=" * 78)
    if gated_fail:
        print(f"  GATE FAILED: {len(gated_fail)} near-miss item(s) regressed to OOD: {gated_fail}")
    else:
        print("  GATE OK: near-miss precision holds; Row 1 residual is measured & accepted.")
    print("=" * 78)
    sys.exit(1 if gated_fail else 0)


if __name__ == "__main__":
    main()
