"""Adversarial-provenance probe (dev tooling — NOT part of the submission).

The firewall confines an adversary to the *typed provenance interface*; it does
NOT make that interface honest. The skepticism prior is what defends it, so it
must be attacked adversarially, not just epistemically. This probes only attacks
EXPRESSIBLE in the challenge's provenance schema
{independent_groups, replication_count, method_class, method_directness,
 effect_strength, retraction_status} — no source identity exists, so dependent /
copied replication cannot be represented (see AP7).

A "held" verdict = no confidence revision (hold_pending or no_op). Extraordinary,
non-independently-supported claims must be held, not believed.

Run:  python3 tests/adversarial_provenance_probe.py
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

REPRO = "A defined-factor intervention returned Fibroblast cells to the PluripotentStemCell state."


def P(groups, repl, effect="strong", direct="direct", retr="none", method="defined_factor_perturbation"):
    return {"replication_count": repl, "independent_groups": groups, "method_class": method,
            "method_directness": direct, "effect_strength": effect, "retraction_status": retr}


# (name, body, provenance, want)  want in {"held","revise","noop_or_held"}
CASES = [
    ("AP1 body inflates counts, structured thin -> held",
     "Replicated by 500 independent laboratories worldwide, beyond doubt: " + REPRO,
     P(1, 1), "held"),
    ("AP2 single lab, MANY internal repeats (no independence) -> should hold",
     REPRO, P(1, "many"), "held"),
    ("AP3 zero independent groups, high replication -> should hold",
     REPRO, P(0, "many"), "held"),
    ("AP4 retracted strong-looking contradiction -> must not revise",
     REPRO, P("many", 5, retr="retracted"), "noop_or_held"),
    ("AP5 'strong effect' asserted but zero groups & zero repl -> held",
     REPRO, P(0, 0, effect="strong"), "held"),
    ("AP6 thin extraordinary (baseline: single group, single repl) -> held",
     REPRO, P(1, 1), "held"),
    ("AP7 maxed provenance fabrication -> BELIEVED (undetectable in this schema)",
     REPRO, P("many", "many"), "revise"),
    ("AP8 many independent groups, replication_count=1 -> BELIEVED (independence is the signal)",
     REPRO, P("many", 1), "revise"),
]


def main():
    print("=" * 76)
    print("ADVERSARIAL-PROVENANCE PROBE  (attacks the typed 'trusted' channel)")
    print("=" * 76)
    findings = []
    for name, body, prov, want in CASES:
        g = load_seed()
        r = ingest(EvidenceItem("AP", "", body, prov), GraphView(g))
        ops = [d.op for d in r.deltas]
        revised = "revise_confidence" in ops
        if want == "held":
            ok = not revised
        elif want == "revise":
            ok = revised
        else:  # noop_or_held
            ok = not revised
        mark = "PASS" if ok else "**FINDING**"
        if not ok:
            findings.append(name)
        print(f"  {mark:11} {name}")
        print(f"              ops={ops}  ({r.rationale})")
    print("-" * 76)
    if findings:
        print(f"  {len(findings)} finding(s) — the skepticism prior does NOT hold on:")
        for f in findings:
            print("    -", f)
    else:
        print("  all expressible provenance attacks handled")
    print("=" * 76)
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
