"""Structural-OOD probe (dev tooling — NOT part of the submission).

Layer 2 (grounding / type-check) upgraded toward E: the transition *type* — in-model
vs off-topology regime — is decided from graph structure (potency, lineage, and the
now-consumed `topological_assumption`), with a lexical cue reserved only for the two
axes the graph genuinely cannot represent (age, function). Two things are pinned here:

  1. `topological_assumption` is actually READ: `_potency_axis_modeled` returns True for
     a potency-declaring domain and False for one that declares neither — so the same
     code type-checks a differently-declared schema instead of baking the axis in.
  2. The near-miss precision guard: when an item names BOTH a lateral (equal-potency,
     distinct-lineage) pair AND a same-lineage potency move, the event is really an
     in-model transition. The OLD rule flagged lateral OOD on the first pair it saw
     (a precision failure); the NEW rule suppresses it. This probe reconstructs the old
     rule inline to measure the difference on a constructed 3-state graph.

Run:  python3 tests/structural_ood_probe.py
"""
from __future__ import annotations
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groundtruth.model import CellState, DomainOfCompetence, BeliefGraph, GraphView
from starter.my_solution import EvidenceFrame, decide_ood, _potency_axis_modeled, _pick


def frame(entities, **kw):
    base = dict(direction=None, reaches_source=False, is_reversion=False,
                is_forward_worded=False, is_lateral=False, is_aging=False,
                is_function=False, identity_preserved=False, is_confirmation=False,
                content_words=set())
    base.update(kw)
    return EvidenceFrame(entities=entities, **base)


def view_with(domain):
    g = BeliefGraph()
    g.domain = domain
    return GraphView(g)


def _old_decide_ood(fr, view):
    """The pre-upgrade rule: flags a lateral pair unconditionally, with no same-lineage
    precision guard and without reading the topology declaration. Kept for contrast."""
    states = fr.entities
    dom = view.domain()
    regimes_not = dom.regimes_not_modeled if dom else []
    axes_excluded = dom.axes_excluded if dom else []
    lateral = any(a.potency_level == c.potency_level and a.lineage_identity != c.lineage_identity
                  for a in states for c in states if a is not c)
    potency_changes = any(a.potency_level != c.potency_level for a in states for c in states if a is not c)
    in_model = fr.reaches_source or potency_changes
    if lateral:
        return "regime", _pick(regimes_not, "lateral_somatic_conversion")
    if not in_model and fr.is_aging:
        return "axis", _pick(axes_excluded, "biological_age")
    return None, None


DOM = DomainOfCompetence(
    entity_types=["CellState"], axes_modeled=["potency", "lineage_identity"],
    axes_excluded=["biological_age", "cell_function_independent_of_identity"],
    regimes_modeled=["differentiation_transition"],
    regimes_not_modeled=["lateral_somatic_conversion", "identity_preserving_state_change"],
    topological_assumption="All transitions move monotonically along the potency axis between adjacent levels.")

DOM_NO_POTENCY = DomainOfCompetence(
    entity_types=["Node"], axes_modeled=["colour"], axes_excluded=[],
    regimes_modeled=[], regimes_not_modeled=["lateral_somatic_conversion"],
    topological_assumption="Nodes are unordered.")


def main() -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")

    print("=" * 76)
    print("STRUCTURAL-OOD PROBE  (topology consumed; near-miss precision guard)")
    print("=" * 76)

    # 1. topological_assumption is actually read
    check("topology read: potency-declaring domain -> axis modeled", _potency_axis_modeled(DOM) is True)
    check("topology read: no-potency domain -> axis NOT modeled", _potency_axis_modeled(DOM_NO_POTENCY) is False)

    # constructed entities
    A = CellState("a", "A", 3, "tissueX")   # terminal, lineage X
    B = CellState("b", "B", 3, "tissueY")   # terminal, lineage Y  (lateral partner of A)
    C = CellState("c", "C", 2, "tissueX")   # progenitor of lineage X (same lineage as A)
    v = view_with(DOM)

    # 2. structural lateral still flags (equal potency, distinct lineage, no same-lineage move)
    lat = decide_ood(frame([A, B], is_lateral=True), v)
    check(f"pure lateral pair -> regime lateral {lat}", lat[0] == "regime" and "lateral" in (lat[1] or ""))

    # 3. clean in-model differentiation (potency move, distinct lineages, no lateral pair) -> not OOD
    inmodel = decide_ood(frame([C, B]), v)   # p2 vs p3, X vs Y -> a potency move
    check(f"in-model potency move -> not flagged {inmodel}", inmodel == (None, None))

    # 4. THE PRECISION WIN: 3 states with a lateral pair AND a same-lineage potency move.
    near = frame([A, B, C], is_lateral=True)
    old = _old_decide_ood(near, v)
    new = decide_ood(near, v)
    check(f"old rule wrongly flags this as OOD  (old={old})", old[0] == "regime")
    check(f"new rule keeps it in-model         (new={new})", new == (None, None))

    print("-" * 76)
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    print("=" * 76)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
