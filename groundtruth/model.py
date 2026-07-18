"""Belief-graph data model.

Lightweight in-memory graph. TypeDB is the production target for Guild; the
harness uses an in-memory model so contestants can run locally without a DB.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import math


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


@dataclass
class CellState:
    id: str
    name: str
    potency_level: int          # 0 totipotent .. 3 terminal (lower = more potent)
    lineage_identity: str


@dataclass
class Claim:
    id: str
    statement: str
    epistemic_status: str        # conjectured|contested|established|refuted|superseded
    confidence: float
    scope: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    derived_from: list[str] = field(default_factory=list)   # for the umbrella claim


@dataclass
class Edge:
    id: str
    frm: str
    to: str
    via: str
    status: str = "established"
    confidence: float = 0.9


@dataclass
class DeclaredAbsence:
    id: str
    frm: str
    to: str
    justified_by: list[str]
    present: bool = False        # promoted to True when an edge is added


@dataclass
class DomainOfCompetence:
    entity_types: list[str]
    axes_modeled: list[str]
    axes_excluded: list[str]
    regimes_modeled: list[str]
    regimes_not_modeled: list[str]
    topological_assumption: str


@dataclass
class BeliefGraph:
    cell_states: dict[str, CellState] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    absences: dict[str, DeclaredAbsence] = field(default_factory=dict)
    entities: dict[str, dict] = field(default_factory=dict)   # e.g. transcription factors
    domain: Optional[DomainOfCompetence] = None
    proposed_regimes: list[str] = field(default_factory=list)
    proposed_axes: list[str] = field(default_factory=list)
    quarantine: list[dict] = field(default_factory=list)
    pending: dict[str, dict] = field(default_factory=dict)    # low-confidence pending claims

    # ---- read helpers (also used by the read-only view) ----
    def get_claim(self, cid: str) -> Optional[Claim]:
        return self.claims.get(cid)

    def cell_by_name(self, name: str) -> Optional[CellState]:
        for cs in self.cell_states.values():
            if cs.name.lower() == name.lower():
                return cs
        return None


class GraphView:
    """Read-only view handed to the contestant ingest function.

    The ingest function can read the belief state but cannot mutate it; the only
    way to affect the world is by returning Deltas. This is the firewall at the
    type level: there is no write method here.
    """
    def __init__(self, graph: BeliefGraph):
        self._g = graph

    def get_claim(self, cid: str) -> Optional[Claim]:
        c = self._g.claims.get(cid)
        if c is None:
            return None
        # return a copy so the caller cannot mutate internal state
        return Claim(c.id, c.statement, c.epistemic_status, c.confidence,
                     dict(c.scope), dict(c.provenance), list(c.evidence_ids), list(c.derived_from))

    def list_claim_ids(self) -> list[str]:
        return list(self._g.claims.keys())

    def cell_state(self, name: str) -> Optional[CellState]:
        return self._g.cell_by_name(name)

    def domain(self) -> Optional[DomainOfCompetence]:
        return self._g.domain

    def pending_ids(self) -> list[str]:
        return list(self._g.pending.keys())

    def has_absence(self, frm: str, to: str) -> bool:
        for a in self._g.absences.values():
            if a.frm == frm and a.to == to:
                return not a.present
        return False
