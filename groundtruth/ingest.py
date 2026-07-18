"""The contestant contract.

Contestants implement an ingest function with this signature. It receives one
evidence item and a READ-ONLY view of the belief state, and returns an
IngestResult. The only way it can change the world is through the deltas it
returns; it has no write access to the graph.

In production the body of ingest is an LLM under constrained decoding for the
extraction step, then symbolic / probabilistic code for the decision step. The
reference implementations here are rule-based stand-ins so the harness runs
offline without a model endpoint.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from .deltas import Delta, no_op
from .model import GraphView


@dataclass
class EvidenceItem:
    id: str
    tag: str                     # hidden at judging; present here for the harness only
    body: str
    provenance: dict             # the ONLY trusted provenance channel
    era: str = ""


@dataclass
class IngestResult:
    deltas: list[Delta] = field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.5
    ood_flag: bool = False


IngestFn = Callable[[EvidenceItem, GraphView], IngestResult]


def stub_ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    """Minimal stub contestants replace. Does nothing."""
    return IngestResult(deltas=[no_op(item.id)], rationale="stub", confidence=0.5, ood_flag=False)
