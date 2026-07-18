"""The scoring harness. Drives an evidence stream through an ingest function,
applying deltas only through the Delta API, and records what happened."""
from __future__ import annotations
from dataclasses import dataclass, field
from .api import DeltaAPI
from .model import BeliefGraph, GraphView
from .ingest import EvidenceItem, IngestFn


@dataclass
class ItemRecord:
    evidence_id: str
    tag: str
    applied_ops: list[str] = field(default_factory=list)
    rejected: list[tuple] = field(default_factory=list)   # (op, reason)
    ood_flag: bool = False
    mutated_state: bool = False
    attempted_mutation: bool = False
    conf_snapshot: dict = field(default_factory=dict)


@dataclass
class RunLog:
    records: list[ItemRecord] = field(default_factory=list)
    structural_violations: list[str] = field(default_factory=list)


MUTATING_OPS = {"revise_confidence", "set_scope", "set_status", "add_claim",
                "add_entity", "add_edge", "drop_claim"}
TRACK_CLAIMS = ["C1", "C2", "C3a", "C3b", "C3c", "C3d", "C3g", "C4", "C5", "C6"]


def run(stream: list[EvidenceItem], ingest_fn: IngestFn, graph: BeliefGraph) -> RunLog:
    api = DeltaAPI(graph)
    log = RunLog()
    for item in stream:
        api.set_active_evidence(item.id)
        view = GraphView(graph)
        # the tag is HIDDEN from your solution at runtime; it exists only for organizer scoring
        public_item = EvidenceItem(item.id, "", item.body, item.provenance, item.era)
        result = ingest_fn(public_item, view)
        rec = ItemRecord(item.id, item.tag, ood_flag=bool(result.ood_flag))
        for d in result.deltas:
            if d.op in MUTATING_OPS:
                rec.attempted_mutation = True   # attempt counts, even if the API rejects it
            res = api.apply(d)
            if res.applied:
                rec.applied_ops.append(d.op)
                if d.op in MUTATING_OPS:
                    rec.mutated_state = True
            else:
                rec.rejected.append((d.op, res.reason))
        rec.conf_snapshot = {c: round(graph.claims[c].confidence, 3)
                             for c in TRACK_CLAIMS if c in graph.claims}
        log.records.append(rec)
    log.structural_violations = list(api.violations)
    return log
