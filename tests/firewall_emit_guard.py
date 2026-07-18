"""Firewall emit guard (dev tooling) — enforces the OUTPUT half of the firewall.

`seam_guard.py` proves the READ side: raw body text is consumed only inside the
perception seam. This guard proves the complementary EMIT side, the property the
whole design rests on:

    Every Delta we ever construct is ATTRIBUTED to the current item — its
    evidence_id is `item.id` and nothing else.

That is the structural reason no input path can emit an unattributed or
cross-item mutation. It is easy to state and easy to erode: the next person who
adds a branch and writes `Delta("...", some_other_id, {...})`, or calls
`_revise(pid, ...)` with a claim/pending id in the evidence slot, silently breaks
attribution while every behavioural test stays green. This guard makes the
invariant checkable by parsing the module and asserting, over EVERY construction
site:

  * `Delta(op, X, ...)`  and  `no_op(X)`  =>  X is `item.id` or the bare `eid`
    parameter (the one indirection: `_revise` forwards its `eid` into `Delta`).
  * every call to `_revise(X, ...)` passes `item.id` as that first `eid` arg.

Together these close the forwarding: the only name a Delta's evidence_id may bind
to is `eid`, and `eid` is only ever `item.id`. Magnitude provenance (that a number
can only come from `strength(prov)`) is enforced separately by the seam guard —
no body-read reaches the arithmetic — so this guard is deliberately scoped to
attribution.

Run:  python3 tests/firewall_emit_guard.py
"""
from __future__ import annotations
import ast
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "starter", "my_solution.py")


def _is_item_id(node) -> bool:
    """True iff the expression is exactly `item.id`."""
    return (isinstance(node, ast.Attribute) and node.attr == "id"
            and isinstance(node.value, ast.Name) and node.value.id == "item")


def _is_allowed_evidence_arg(node) -> bool:
    """The evidence_id slot may be `item.id` directly, or the bare `eid` name —
    the single forwarding parameter, whose own call sites are checked separately."""
    return _is_item_id(node) or (isinstance(node, ast.Name) and node.id == "eid")


def _callee_name(call: ast.Call):
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def main():
    src = open(SRC, encoding="utf-8").read()
    tree = ast.parse(src)
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node)

        if name == "Delta":
            # Delta(op, evidence_id, payload=...)
            if len(node.args) < 2 or not _is_allowed_evidence_arg(node.args[1]):
                got = ast.dump(node.args[1]) if len(node.args) >= 2 else "<missing>"
                violations.append(("Delta", node.lineno, got))

        elif name == "no_op":
            # no_op(evidence_id)
            if not node.args or not _is_allowed_evidence_arg(node.args[0]):
                got = ast.dump(node.args[0]) if node.args else "<missing>"
                violations.append(("no_op", node.lineno, got))

        elif name == "_revise":
            # _revise(eid, claim, s_scaled, direction) — the eid must be item.id
            if not node.args or not _is_item_id(node.args[0]):
                got = ast.dump(node.args[0]) if node.args else "<missing>"
                violations.append(("_revise", node.lineno, got))

    print("=" * 66)
    print("FIREWALL EMIT GUARD  (every Delta is attributed to the current item)")
    print("=" * 66)
    if not violations:
        print("  PASS  every Delta/no_op evidence_id is item.id (or the forwarded eid),")
        print("        and every _revise() is called with item.id")
    else:
        for kind, line, got in violations:
            print(f"  FAIL  {kind}() at line {line} — evidence_id is not item.id/eid: {got}")
    print("=" * 66)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
