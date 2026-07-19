"""LLR calibration probe (dev tooling — NOT part of the submission).

Layer 3 (probabilistic reasoning) upgraded A -> E: the calibration is now an explicit
**additive log-likelihood-ratio pool** (`llr_breakdown`) rather than an opaque tuned
scalar. This probe pins the properties that make it a genuine Bayesian evidence pool,
and that the resulting update has the trajectory *shape* the rubric grades:

  * additivity        S == groups-term + repl-term (clamped)
  * monotonicity      more independent groups / replications never lowers S
  * independence      an extra independent group raises S more than an extra internal
                      replication (independence is the least-gameable dimension)
  * saturation        beyond the cap, more replication adds nothing (spoof-resistant)
  * quality scaling   indirect < direct, weak < strong effect
  * null -> zero      a null/absent effect contributes no evidence
  * ordering          strong > moderate > weak  (the graded magnitude order)
  * prior-aware       the SAME evidence moves a contested prior far more, in
                      probability, than a near-certain one (log-odds compression)

Run:  python3 tests/llr_calibration_probe.py
"""
from __future__ import annotations
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starter.my_solution import strength, llr_breakdown, MAX_MOVE, EPS
from groundtruth.model import logit, sigmoid


def P(groups=0, repl=0, direct="direct", effect="strong"):
    return {"independent_groups": groups, "replication_count": repl,
            "method_directness": direct, "effect_strength": effect}


def main() -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")

    print("=" * 74)
    print("LLR CALIBRATION PROBE  (additive log-likelihood-ratio pool, graded shape)")
    print("=" * 74)

    # additivity: S is exactly the sum of the per-dimension LLR terms
    b = llr_breakdown(P(4, 5))
    check("additive: S == groups + repl terms",
          abs(strength(P(4, 5)) - min(1.0, b["groups"] + b["repl"])) < 1e-12)

    # monotonicity in each quantity dimension
    check("monotone in independent_groups",
          strength(P(1, 2)) <= strength(P(2, 2)) <= strength(P(4, 2)) <= strength(P(6, 2)))
    check("monotone in replication_count",
          strength(P(2, 1)) <= strength(P(2, 3)) <= strength(P(2, 6)))

    # independence dominates internal replication (weight 0.65 vs 0.35)
    check("an extra independent group > an extra internal replication",
          (strength(P(3, 2)) - strength(P(2, 2))) > (strength(P(2, 3)) - strength(P(2, 2))))

    # saturation: a spoofed huge count is no stronger than the cap
    check("saturates (6 groups == 100 groups)", strength(P(6, 6)) == strength(P(100, 100)))

    # quality scaling
    check("indirect method < direct", strength(P(4, 4, direct="indirect")) < strength(P(4, 4, direct="direct")))
    check("weak effect < strong effect", strength(P(4, 4, effect="weak")) < strength(P(4, 4, effect="strong")))
    check("null/absent effect contributes zero", strength(P(6, 6, effect="none")) == 0.0)

    # graded ordering: strong > moderate > weak, and weak/indirect is below the noise gate
    strong = strength(P(4, 5, effect="strong"))
    moderate = strength(P(2, 2, effect="moderate"))
    weak = strength(P(2, 1, direct="indirect", effect="weak"))
    check(f"ordering strong({strong:.2f}) > moderate({moderate:.2f}) > weak({weak:.2f})",
          strong > moderate > weak)
    check(f"weak,indirect below the epsilon noise gate (|Δlogit|={MAX_MOVE*weak:.3f} < {EPS})",
          MAX_MOVE * weak < EPS)

    # prior-awareness: identical evidence, different priors -> the contested belief
    # moves far more in probability than the near-certain one (log-odds compression).
    S = strength(P(4, 5))
    move_contested = sigmoid(logit(0.55) - MAX_MOVE * S) - 0.55
    move_certain = sigmoid(logit(0.97) - MAX_MOVE * S) - 0.97
    check(f"prior-aware: |Δp@0.55|={abs(move_contested):.2f} > |Δp@0.97|={abs(move_certain):.2f}",
          abs(move_contested) > abs(move_certain))

    print("-" * 74)
    print("  ALL PASS" if ok else "  FAILURES ABOVE")
    print("=" * 74)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
