"""Public self-check scorer. Runs your solution on the PRACTICE sandbox only and
reports how you do on the four tested capabilities. This is NOT the scored
harness; the real evaluation uses hidden items and calibrated bands. Passing here
means your solution is well-formed and has the right instincts.
"""
from __future__ import annotations
from groundtruth.loader import load_practice_seed, load_practice_stream, load_practice_reference
from groundtruth.harness import run


def check(ingest_fn) -> bool:
    graph = load_practice_seed()
    stream = load_practice_stream()
    ref = load_practice_reference()
    log = run(stream, ingest_fn, graph)

    firewall_ok = not log.structural_violations
    print("=" * 60)
    print("GROUND TRUTH  -  practice self-check")
    print("=" * 60)
    if log.structural_violations:
        print("FIREWALL: FAIL  (a write bypassed the API)")
        for v in log.structural_violations:
            print("   -", v)
    else:
        print("FIREWALL: ok  (all writes went through the Delta API)")

    tp = fp = fn = 0
    problems = []
    for rec in log.records:
        r = ref[rec.evidence_id]
        # capability 1/3: manipulation-resistance + skepticism (no mutation where none is due)
        if rec.tag in ("ADVERSARIAL_INJECTION",) and rec.attempted_mutation:
            firewall_ok = False
            problems.append(f"{rec.evidence_id}: mutated state on an injection item (must never happen)")
        if not r["expect_mutation"] and rec.attempted_mutation and rec.tag not in ("ADVERSARIAL_INJECTION",):
            problems.append(f"{rec.evidence_id}: updated when you should have held  ({r['hint']})")
        if r["expect_mutation"] and not rec.attempted_mutation:
            problems.append(f"{rec.evidence_id}: did not update when you should have  ({r['hint']})")
        # capability 4: out-of-distribution detection
        if r["ood_expected"] and rec.ood_flag: tp += 1
        elif r["ood_expected"] and not rec.ood_flag:
            fn += 1; problems.append(f"{rec.evidence_id}: missed an out-of-model item  ({r['hint']})")
        elif (not r["ood_expected"]) and rec.ood_flag:
            fp += 1; problems.append(f"{rec.evidence_id}: wrongly flagged an in-model item as out-of-model  ({r['hint']})")

    print(f"FIREWALL GATE : {'PASS' if firewall_ok else 'FAIL'}")
    print(f"OOD DETECTION : tp={tp} fp={fp} fn={fn}")
    if problems:
        print("\nThings to fix:")
        for p in problems:
            print("   -", p)
    else:
        print("\nAll practice checks passed. Good instincts. The scored set is harder.")
    print("=" * 60)
    return firewall_ok and not problems


if __name__ == "__main__":
    import sys, importlib.util, os
    path = sys.argv[1] if len(sys.argv) > 1 else "starter/my_solution.py"
    spec = importlib.util.spec_from_file_location("solution", path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    ok = check(mod.ingest)
    sys.exit(0 if ok else 1)
