"""Seam guard (dev tooling) — enforces the perception boundary structurally.

The whole value of the EvidenceFrame refactor is that raw evidence text is read in
exactly ONE place (`extract`, plus the trusted firewall scanner). That is easy to
state and easy to erode: the next person who "just adds a keyword" in the decision
core silently reopens the brittleness we spent three rounds closing. This test makes
the invariant checkable instead of aspirational: it parses the module and asserts
that the raw-text signal vocabulary (keyword lists, text regexes, the 'differentiat'
literal) appears only inside allowlisted perception/firewall functions.

If this fails, you added a body-read outside the seam. Move it into `extract`
(as a new EvidenceFrame field) rather than reading text in the decision layer.

Run:  python3 tests/seam_guard.py
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

# Functions permitted to read raw text: the perception layer and the trusted
# firewall scanner. Everything else must consume the EvidenceFrame.
ALLOWED = {
    "extract", "find_states", "transition_direction",
    "_state_mentions", "_mention_spans", "_singular",
    "_normalize_for_scan", "looks_like_injection",
    # clause/polarity/modality perception helpers (all consumed only by extract)
    "_split_clauses", "_neg_split", "_has_rev", "_scan_reversion",
}

# The vocabulary of raw-text reading. A leaked body-read references one of these
# keyword/regex identifiers, or matches the bare 'differentiat' literal, as CODE.
FORBIDDEN_NAMES = {
    "_SOURCE_KW", "_LATERAL_KW", "_AGE_KW", "_FUNC_KW", "_CONFIRM_KW",
    "_IDENTITY_PRESERVED_RE", "_DIR_CONNECTIVE", "_ACTIVE_PRODUCTION", "_ORIGIN_CUE",
    "_REV_VERBS", "_REV_DESCRIPTORS", "_NEG_RE", "_NEG_TERM", "_HYP_RE",
    "_COMPARATIVE_RE", "_CHANGE_VERB_RE", "_TRANSITION_VERB_RE",
    "_ENTITY_WORD", "_CAMEL_PART",
}
FORBIDDEN_STR = "differentiat"


def _docstring_node(fn):
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        return body[0].value
    return None


def main():
    src = open(SRC, encoding="utf-8").read()
    tree = ast.parse(src)
    violations = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name in ALLOWED:
            continue
        doc = _docstring_node(fn)
        # Inspect real AST nodes (identifiers + string literals), so comments and
        # docstrings — which are not code — never trip the guard.
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                violations.append((fn.name, node.id, node.lineno))
            elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and node is not doc and FORBIDDEN_STR in node.value):
                violations.append((fn.name, repr(node.value), node.lineno))

    print("=" * 66)
    print("SEAM GUARD  (raw-text reads must live only in the perception layer)")
    print("=" * 66)
    print(f"  allowlisted readers: {', '.join(sorted(ALLOWED))}")
    if not violations:
        print("  PASS  no raw-text signal is read outside the perception/firewall seam")
    else:
        for name, tok, line in violations:
            print(f"  FAIL  {name}() reads {tok} (line {line}) — move it into extract()")
    print("=" * 66)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
