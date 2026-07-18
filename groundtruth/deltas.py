"""The closed, typed delta vocabulary.

State can only change through these. A delta is a structured object, never a
string, so injected instruction text cannot express a mutation. Anything not in
OPS is rejected by the API.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

OPS = {
    "no_op",                 # explicitly do nothing (confirms, rejected injections)
    "revise_confidence",     # {claim_id, new_confidence}
    "set_scope",             # {claim_id, scope}
    "set_status",            # {claim_id, status}
    "add_claim",             # {claim_id, statement, status, confidence, scope}
    "add_entity",            # {entity_id, entity_type, data}
    "add_edge",              # {from, to, via}  (promotes a declared absence)
    "drop_claim",            # {claim_id}
    "propose_regime",        # {regime}
    "propose_axis",          # {axis}
    "quarantine",            # {reference}
    "hold_pending",          # {claim_id, note}  (low-confidence pending, not a graph mutation)
}


@dataclass
class Delta:
    op: str
    evidence_id: str
    payload: dict[str, Any] = field(default_factory=dict)


def no_op(evidence_id: str) -> Delta:
    return Delta("no_op", evidence_id, {})
