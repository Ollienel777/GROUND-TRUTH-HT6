"""Entity-extraction probe (dev tooling — NOT part of the submission).

Pins the widened `find_states`: the classifier must resolve a graph state named in
the body when it appears (a) lowercase ('fibroblast'), (b) pluralised
('Fibroblasts', 'neurons'), or (c) as a spaced phrase ('pluripotent stem cell'),
not only as a bare CamelCase token. This closes the residual gap DESIGN.md calls
out ("find_states is CamelCase-only, so lowercase multi-word entity phrases still
lean on _SOURCE_KW").

Resolution stays STRUCTURAL: only an exact case-insensitive match to a real state
name in the read-only view resolves, so nothing is invented (renamed_seed_probe is
still 12/12 identical). The decisive case is a reprogramming worded with neither a
reversion keyword nor a 'from' cue and with lowercase entity names — the OLD
CamelCase-only extractor returned no states, so the whole pipeline fell through to
no_op: a silent FALSE NEGATIVE on the 40-pt revision axis. It is now grounded on
entity potency and revised.

Run:  python3 tests/entity_extraction_probe.py
"""
from __future__ import annotations
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groundtruth.loader import load_seed
from groundtruth.model import GraphView
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest, find_states, transition_direction


def _old_find_states(view, body):
    """The pre-fix extractor: bare CamelCase tokens only. Kept here to demonstrate,
    not to use — the regression this probe guards is measured against it."""
    seen, out = set(), []
    for tok in re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\b", body):
        if tok in seen:
            continue
        seen.add(tok)
        cs = view.cell_state(tok)
        if cs is not None:
            out.append(cs)
    return out


def P(groups=4, repl=5, method="defined_factor_perturbation",
      direct="direct", effect="strong", retr="none"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


def main() -> bool:
    g = load_seed()
    view = GraphView(g)
    ok = True

    print("=" * 74)
    print("ENTITY EXTRACTION PROBE  (lowercase / plural / spaced names resolve)")
    print("=" * 74)

    # ---- unit: find_states resolves the varied forms -----------------------
    unit = [
        ("lowercase single word",      "a fibroblast was observed",              {"Fibroblast"}),
        ("plural",                     "Treated Fibroblasts and Neurons",        {"Fibroblast", "Neuron"}),
        ("spaced CamelCase phrase",    "a pluripotent stem cell colony",         {"PluripotentStemCell"}),
        ("spaced + plural",            "pluripotent stem cells were seen",       {"PluripotentStemCell"}),
        ("mixed case + camel token",   "fibroblast -> PluripotentStemCell",      {"Fibroblast", "PluripotentStemCell"}),
        ("no entity present",          "an assay measured something generic",    set()),
    ]
    for label, body, want in unit:
        got = {s.name for s in find_states(view, body)}
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label:<28} got={sorted(got)}")

    # ---- unit: direction resolves for lowercase / spaced pairs -------------
    dir_cases = [
        ("lowercase reprogramming (into)", "fibroblast cells were converted into pluripotent stem cells", "backward"),
        ("spaced forward differentiation", "pluripotent stem cells gave rise to fibroblast cells",         "forward"),
    ]
    for label, body, want in dir_cases:
        st = find_states(view, body)
        got = transition_direction(body.lower(), st)
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label:<32} dir={got} (want {want})")

    # ---- regression: the case the OLD extractor silently dropped -----------
    print("-" * 74)
    body = "A defined-factor intervention converted fibroblast cells into pluripotent stem cells."
    old_states = {s.name for s in _old_find_states(view, body)}
    new_states = {s.name for s in find_states(view, body)}
    demo = (old_states == set()) and ({"Fibroblast", "PluripotentStemCell"} <= new_states)
    ok &= demo
    print(f"  {'PASS' if demo else 'FAIL'}  old extractor saw {sorted(old_states)}; "
          f"new sees {sorted(new_states)}")

    res = ingest(EvidenceItem("R1", "", body, P()), GraphView(load_seed()))
    ops = [d.op for d in res.deltas]
    revised = "revise_confidence" in ops and not res.ood_flag
    ok &= revised
    print(f"  {'PASS' if revised else 'FAIL'}  end-to-end now revises (ops={ops}, ood={res.ood_flag})")

    # ---- guard: lowercase FORWARD differentiation must NOT be a revision ----
    fwd = ingest(EvidenceItem("R2", "",
                 "pluripotent stem cells differentiated into fibroblast cells under standard conditions.",
                 P(method="observational")), GraphView(load_seed()))
    fwd_ops = [d.op for d in fwd.deltas]
    fwd_ok = "revise_confidence" not in fwd_ops and not fwd.ood_flag
    ok &= fwd_ok
    print(f"  {'PASS' if fwd_ok else 'FAIL'}  lowercase forward differentiation held (ops={fwd_ops})")

    print("-" * 74)
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    print("=" * 74)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
