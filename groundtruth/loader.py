"""Loads the seed graph and evidence stream from JSON."""
from __future__ import annotations
import json, os
from .model import BeliefGraph, CellState, Claim, DeclaredAbsence, DomainOfCompetence
from .ingest import EvidenceItem

_HERE = os.path.dirname(__file__)


def load_seed(path: str | None = None) -> BeliefGraph:
    path = path or os.path.join(_HERE, "data", "seed.json")
    d = json.load(open(path))
    g = BeliefGraph()
    for cs in d["cell_states"]:
        g.cell_states[cs["id"]] = CellState(**cs)
    for c in d["claims"]:
        g.claims[c["id"]] = Claim(
            c["id"], c["statement"], c["epistemic_status"], c["confidence"],
            c.get("scope", {}), c.get("provenance", {}), c.get("evidence_ids", []),
            c.get("derived_from", []))
    for a in d["absences"]:
        g.absences[a["id"]] = DeclaredAbsence(a["id"], a["frm"], a["to"], a["justified_by"])
    dm = d["domain"]
    g.domain = DomainOfCompetence(dm["entity_types"], dm["axes_modeled"], dm["axes_excluded"],
                                  dm["regimes_modeled"], dm["regimes_not_modeled"],
                                  dm["topological_assumption"])
    return g


def load_stream(path: str | None = None) -> list[EvidenceItem]:
    path = path or os.path.join(_HERE, "data", "stream.json")
    return [EvidenceItem(i["id"], i["tag"], i["body"], i["provenance"], i.get("era", ""))
            for i in json.load(open(path))]


def load_practice_seed() -> BeliefGraph:
    return load_seed(os.path.join(_HERE, "data", "practice_seed.json"))


def load_practice_stream() -> list[EvidenceItem]:
    return load_stream(os.path.join(_HERE, "data", "practice_stream.json"))


def load_practice_reference() -> dict:
    return json.load(open(os.path.join(_HERE, "data", "practice_reference.json")))
