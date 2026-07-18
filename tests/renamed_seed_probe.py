"""Renamed-seed / format-portability harness (dev tooling — NOT part of the submission).

The domain block is byte-identical between the practice and real seeds while the
entity names differ. This runs the 12-item hard stream under a MATRIX of surface
transforms and asserts every verdict/trajectory is identical to the canonical
baseline. Any DIFFER is entity-name or token-FORMAT coupling we didn't know we had.

Two portability threats are exercised:

  * RENAMED  — the hidden graph uses different entity NAMES (both graph and body
    renamed consistently). Varies the *format* of those names: CamelCase tokens,
    lowercase, spaced, hyphenated. `find_states` must extract whatever surface
    form the names take.
  * BODY-ONLY REFORMAT — the graph keeps its canonical CamelCase names, but the
    body refers to entities in a different surface form ("pluripotent stem cell"
    for `PluripotentStemCell`). This is the harder case: it exercises the despaced
    match ("pluripotent stem cell" -> "pluripotentstemcell" == canonical, folded)
    AND `transition_direction`, which must locate a state whose canonical name is
    NOT a literal substring of the reformatted body.

Run:  python3 tests/renamed_seed_probe.py
"""
from __future__ import annotations
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from groundtruth.loader import load_seed
from groundtruth.harness import run
from groundtruth.ingest import EvidenceItem
from starter.my_solution import ingest
from hard_selfcheck import STREAM  # reuse the 12-item stream + expectations

# The canonical entity names present in the seed and referenced in the stream.
CANON = [
    "PluripotentStemCell", "MesodermalProgenitor", "Fibroblast",
    "SkeletalMuscleCell", "Neuron", "IntestinalEpithelialCell",
]

# Arbitrary renamed tokens (threat 1); the *format* is applied on top of these.
RENAME = {
    "PluripotentStemCell": "Alpha", "MesodermalProgenitor": "Bravo",
    "Fibroblast": "Charlie", "SkeletalMuscleCell": "Delta",
    "Neuron": "Echo", "IntestinalEpithelialCell": "Foxtrot",
}

_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _words(name: str):
    """Break a CamelCase-ish token into its words: PluripotentStemCell -> [...]."""
    return _CAMEL_SPLIT.sub(" ", name).split()


def _fmt(name: str, style: str) -> str:
    """Render a canonical name in a surface format."""
    if style == "camel":
        return name
    if style == "lower":       # single lowercase token: pluripotentstemcell
        return "".join(_words(name)).lower()
    if style == "spaced":      # pluripotent stem cell
        return " ".join(_words(name)).lower()
    if style == "hyphen":      # pluripotent-stem-cell
        return "-".join(_words(name)).lower()
    if style == "titlespaced": # Pluripotent Stem Cell
        return " ".join(_words(name))
    raise ValueError(style)


def _reformat_text(text: str, style: str, base=None) -> str:
    """Replace each canonical name in `text` with its `style` form. If `base` is
    given (the rename map), the canonical is first renamed, then formatted."""
    for canon in CANON:
        src = (base or {}).get(canon, canon)
        text = text.replace(canon, _fmt(src, style))
    return text


# Each variant: (label, rename_map_or_None, body_style, name_style).
#   rename_map None  -> graph keeps canonical names (body-only reformat threat)
#   rename_map RENAME-> graph+body renamed to arbitrary tokens (rename threat)
# name_style formats the GRAPH cell_state/absence names; body_style the body text.
VARIANTS = [
    ("baseline",         None,   "camel",  "camel"),
    # body-only reformat: graph stays canonical CamelCase, body varies
    ("body-lower",       None,   "lower",  "camel"),
    ("body-spaced",      None,   "spaced", "camel"),
    ("body-hyphen",      None,   "hyphen", "camel"),
    ("body-titlespaced", None,   "titlespaced", "camel"),
    # renamed graph+body, in varied formats
    ("rename-camel",     RENAME, "camel",  "camel"),
    ("rename-lower",     RENAME, "lower",  "lower"),
    ("rename-spaced",    RENAME, "spaced", "spaced"),
    ("rename-hyphen",    RENAME, "hyphen", "hyphen"),
]


def run_variant(rename_map, body_style, name_style):
    g = load_seed()
    if name_style != "camel" or rename_map is not None:
        rn = {c: _fmt((rename_map or {}).get(c, c), name_style) for c in CANON}
        for cs in g.cell_states.values():
            cs.name = rn.get(cs.name, cs.name)
        for a in g.absences.values():
            a.frm = rn.get(a.frm, a.frm)
            a.to = rn.get(a.to, a.to)
    stream = [EvidenceItem(it.id, "", _reformat_text(it.body, body_style, rename_map),
                           it.provenance, it.era)
              for it, _ in STREAM]
    return run(stream, ingest, g).records


def signature(rec):
    return (rec.attempted_mutation, rec.ood_flag, tuple(sorted(set(rec.applied_ops))),
            tuple(sorted(rec.conf_snapshot.items())))


def main():
    base = run_variant(None, "camel", "camel")
    base_sig = [signature(r) for r in base]

    print("=" * 78)
    print("RENAMED / FORMAT-PORTABILITY PROBE  (surface transforms; verdicts must match)")
    print("=" * 78)
    all_ok = True
    for label, rmap, bstyle, nstyle in VARIANTS:
        recs = run_variant(rmap, bstyle, nstyle)
        diffs = []
        for (it, _), b_sig, r in zip(STREAM, base_sig, recs):
            if signature(r) != b_sig:
                diffs.append((it.id, r))
        n = len(STREAM) - len(diffs)
        status = "OK  " if not diffs else "FAIL"
        print(f"  {status}  {label:16} {n}/{len(STREAM)} identical")
        for iid, r in diffs:
            print(f"            DIFFER {iid:4} ood={r.ood_flag} ops={sorted(set(r.applied_ops))}")
        all_ok = all_ok and not diffs
    print("-" * 78)
    print(f"  {'ALL VARIANTS MATCH BASELINE' if all_ok else 'FORMAT COUPLING DETECTED'}")
    print("=" * 78)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
