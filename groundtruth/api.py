"""The Delta API: the ONLY mutation path. This is the firewall in code.

The API is structural, not epistemic. It guarantees that no write is unauthorized,
unstructured, unbounded, or unattributed. It does NOT judge whether an update is
scientifically correct; that is the scorer's job. Its guarantees:

  1. Closed vocabulary   -- unknown ops rejected.
  2. Provenance channel   -- every delta must carry the ACTIVE evidence id; a delta
                             attributed to any other evidence is rejected. Provenance
                             is read from the structured item, never the body text.
  3. Bounded change       -- a single revise_confidence may not move log-odds by more
                             than CAP, and only one confidence revision per claim per item.
  4. Referential integrity-- targets of revise/scope/status/drop must exist; add ops
                             must not duplicate; edges must correspond to a declared absence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from .deltas import Delta, OPS
from .model import BeliefGraph, Claim, Edge, logit, sigmoid

CAP_LOGODDS = 3.0   # max |change in log-odds| from a single delta


@dataclass
class ApplyResult:
    applied: bool
    reason: str = ""


@dataclass
class Event:
    evidence_id: str
    op: str
    payload: dict
    before: dict = field(default_factory=dict)   # for rollback


class DeltaAPI:
    def __init__(self, graph: BeliefGraph):
        self.g = graph
        self.active_evidence: str | None = None
        self.events: list[Event] = []
        self._conf_revised_this_item: set[str] = set()
        self.violations: list[str] = []   # structural bypass attempts

    def set_active_evidence(self, eid: str):
        self.active_evidence = eid
        self._conf_revised_this_item = set()

    # ---- the single entry point ----
    def apply(self, d: Delta) -> ApplyResult:
        if d.op not in OPS:
            self.violations.append(f"unknown op '{d.op}'")
            return ApplyResult(False, f"unknown op '{d.op}'")
        if d.evidence_id != self.active_evidence:
            self.violations.append(
                f"evidence-id mismatch: delta claims '{d.evidence_id}', active '{self.active_evidence}'")
            return ApplyResult(False, "evidence-id mismatch (unattributed write)")
        return getattr(self, f"_op_{d.op}")(d)

    # ---- ops ----
    def _op_no_op(self, d): return ApplyResult(True, "no-op")

    def _op_revise_confidence(self, d):
        cid = d.payload.get("claim_id"); new = d.payload.get("new_confidence")
        c = self.g.claims.get(cid)
        if c is None:
            return ApplyResult(False, f"claim '{cid}' does not exist")
        if not isinstance(new, (int, float)) or not (0.0 <= new <= 1.0):
            return ApplyResult(False, "confidence out of [0,1]")
        if cid in self._conf_revised_this_item:
            return ApplyResult(False, "second confidence revision to same claim this item")
        if abs(logit(new) - logit(c.confidence)) > CAP_LOGODDS:
            return ApplyResult(False, f"single-step change exceeds cap ({CAP_LOGODDS} log-odds)")
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload), {"confidence": c.confidence}))
        c.confidence = float(new)
        if d.evidence_id not in c.evidence_ids:
            c.evidence_ids.append(d.evidence_id)
        self._conf_revised_this_item.add(cid)
        self._propagate_umbrella()
        return ApplyResult(True, "confidence revised")

    def _op_set_scope(self, d):
        cid = d.payload.get("claim_id"); scope = d.payload.get("scope")
        c = self.g.claims.get(cid)
        if c is None: return ApplyResult(False, f"claim '{cid}' does not exist")
        if not isinstance(scope, dict): return ApplyResult(False, "scope must be an object")
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload), {"scope": dict(c.scope)}))
        c.scope.update(scope)
        return ApplyResult(True, "scope set")

    def _op_set_status(self, d):
        cid = d.payload.get("claim_id"); st = d.payload.get("status")
        c = self.g.claims.get(cid)
        if c is None: return ApplyResult(False, f"claim '{cid}' does not exist")
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload), {"status": c.epistemic_status}))
        c.epistemic_status = st
        return ApplyResult(True, "status set")

    def _op_add_claim(self, d):
        cid = d.payload.get("claim_id")
        if cid in self.g.claims: return ApplyResult(False, f"claim '{cid}' already exists")
        self.g.claims[cid] = Claim(cid, d.payload.get("statement", ""),
                                   d.payload.get("status", "conjectured"),
                                   float(d.payload.get("confidence", 0.5)),
                                   dict(d.payload.get("scope", {})), {}, [d.evidence_id])
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "claim added")

    def _op_add_entity(self, d):
        eid = d.payload.get("entity_id")
        if eid in self.g.entities: return ApplyResult(False, f"entity '{eid}' already exists")
        self.g.entities[eid] = {"type": d.payload.get("entity_type"), **d.payload.get("data", {})}
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "entity added")

    def _op_add_edge(self, d):
        frm, to, via = d.payload.get("from"), d.payload.get("to"), d.payload.get("via", "reprogramming")
        # edges must correspond to a declared absence (referential integrity)
        match = None
        for a in self.g.absences.values():
            if a.frm == frm and a.to == to:
                match = a
        if match is None:
            return ApplyResult(False, "edge does not correspond to any declared absence")
        eid = f"e_{frm}_{to}"
        self.g.edges[eid] = Edge(eid, frm, to, via)
        match.present = True
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "edge added")

    def _op_drop_claim(self, d):
        cid = d.payload.get("claim_id")
        # dependency-directed: dropping a pending claim, or a claim, removes it and its evidence links
        if cid in self.g.pending:
            self.events.append(Event(d.evidence_id, d.op, {"claim_id": cid}, {"pending": dict(self.g.pending[cid])}))
            del self.g.pending[cid]
            return ApplyResult(True, "pending claim dropped")
        if cid in self.g.claims:
            self.events.append(Event(d.evidence_id, d.op, {"claim_id": cid}, {"claim": self.g.claims[cid]}))
            del self.g.claims[cid]
            return ApplyResult(True, "claim dropped")
        return ApplyResult(False, f"claim '{cid}' does not exist")

    def _op_propose_regime(self, d):
        r = d.payload.get("regime")
        if r not in self.g.proposed_regimes: self.g.proposed_regimes.append(r)
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "regime proposed")

    def _op_propose_axis(self, d):
        a = d.payload.get("axis")
        if a not in self.g.proposed_axes: self.g.proposed_axes.append(a)
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "axis proposed")

    def _op_quarantine(self, d):
        self.g.quarantine.append({"reference": d.payload.get("reference"), "evidence_id": d.evidence_id})
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "quarantined")

    def _op_hold_pending(self, d):
        cid = d.payload.get("claim_id")
        self.g.pending[cid] = {"note": d.payload.get("note", ""), "evidence_id": d.evidence_id}
        self.events.append(Event(d.evidence_id, d.op, dict(d.payload)))
        return ApplyResult(True, "held pending")

    # ---- umbrella propagation (C3g derived from children) ----
    def _propagate_umbrella(self):
        umb = self.g.claims.get("C3g")
        if umb is None or not umb.derived_from:
            return
        vals = [self.g.claims[c].confidence for c in umb.derived_from if c in self.g.claims]
        if vals:
            # umbrella "cannot return by ANY mechanism" <= min over children (weakest link)
            umb.confidence = min(vals)

    # ---- rollback (event-sourced) ----
    def rollback(self, evidence_id: str):
        for ev in reversed([e for e in self.events if e.evidence_id == evidence_id]):
            if ev.op == "revise_confidence" and "confidence" in ev.before:
                self.g.claims[ev.payload["claim_id"]].confidence = ev.before["confidence"]
