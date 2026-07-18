"""Battery runner (dev tooling — NOT part of the submission).

Runs every probe/guard in tests/ as a subprocess and aggregates a single
pass/fail. Two of the tracks depend on this being a reliable gate:

  * Firewall regression gate (#1): firewall_emit_guard + seam_guard must run on
    every push so a future branch cannot silently break attribution while the
    behavioural tests stay green.
  * Coverage audit (#5): the format-robustness, OOD sub-type, direction, and
    hard-selfcheck probes together assert every gradable in-model contradiction
    maps to a revision, every OOD category is caught, and nothing gradable
    silently falls to no_op. One command re-confirms the whole surface.

Every probe now signals its own verdict via EXIT CODE (0 pass / non-zero fail),
so the runner keys off the return code. The stdout parse (failure markers and
"m/n" tallies with m < n) is kept only as a BACKUP net for any probe that is ever
added without a proper exit code — it never overrides a clean exit-0 into a pass,
only catches a probe that forgot to fail.

Run:  python3 tests/run_battery.py     (exit 0 iff every probe passes)
"""
from __future__ import annotations
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# All probes/guards. hard_selfcheck is a scoring report; the rest are assertions.
PROBES = [
    "seam_guard", "firewall_emit_guard",
    "renamed_seed_probe", "paraphrase_probe", "extract_probe",
    "direction_probe", "polarity_probe",
    "ood_subtype_probe", "skepticism_probe",
    "adversarial_probe", "adversarial_provenance_probe",
    "malformed_provenance_probe", "trajectory_probe",
    "calibration_probe", "sequence_probe",
    "hard_selfcheck",
]

# Probes expected on an in-flight branch but not yet in this tree. Any listed here
# is auto-included the moment its file lands (no edit to PROBES needed) and, until
# then, reported as "pending" — never counted as a pass, so a genuinely deleted
# probe still surfaces as missing instead of silently dropping out of the gate.
# Empty now that PR #3's calibration/sequence probes have merged into PROBES above.
PENDING_PROBES = []

# A failure shows up one of three ways. Verdict words (FAIL/DIFFER) are matched
# LINE-ANCHORED so explanatory header prose ("FAIL = a real blind spot") and
# "XFAIL" (a tracked/expected hole) are not mistaken for a failing run. The rest
# are substrings that only ever appear on a genuine failure.
_FAIL_LINE = re.compile(r"^\s*(?:FAIL|DIFFER)\b", re.MULTILINE)
_FAIL_SUBSTR = (
    re.compile(r"\bBAD\b"),                 # hard_selfcheck magnitude-ordering failure
    re.compile(r"disqualif", re.IGNORECASE),
    re.compile(r"COUPLING DETECTED"),
)
_TALLY = re.compile(r"\b(\d+)/(\d+)\b")


def _failed(code: int, out: str) -> bool:
    # Return code is the primary signal; the stdout parse is a backup for any probe
    # that ever forgets to exit non-zero on failure.
    if code != 0:
        return True
    if _FAIL_LINE.search(out) or any(rx.search(out) for rx in _FAIL_SUBSTR):
        return True
    return any(int(m) < int(n) for m, n in _TALLY.findall(out))


def main():
    print("=" * 70)
    print("BATTERY  (all probes + guards must pass)")
    print("=" * 70)
    # Auto-include any pending probe whose file has since landed in the tree.
    active = list(PROBES) + [p for p in PENDING_PROBES
                             if os.path.exists(os.path.join(HERE, f"{p}.py"))]
    pending = [p for p in PENDING_PROBES if p not in active]
    failures = []
    for name in active:
        path = os.path.join(HERE, f"{name}.py")
        r = subprocess.run([sys.executable, path], cwd=ROOT,
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        bad = _failed(r.returncode, out)
        print(f"  {'FAIL' if bad else 'ok  '}  {name}")
        if bad:
            failures.append(name)
            for line in out.strip().splitlines()[-6:]:
                print(f"          | {line}")
    for name in pending:
        print(f"  ....  {name}  (pending — not yet in this branch)")
    print("-" * 70)
    if failures:
        print(f"  {len(failures)} FAILED: {', '.join(failures)}")
    else:
        print(f"  ALL {len(active)} PROBES PASS")
    if pending:
        print(f"  {len(pending)} pending (auto-activate on merge): {', '.join(pending)}")
    print("=" * 70)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
