"""YOUR SOLUTION GOES HERE.

Implement ingest(item, view). It is called once per evidence item, in order.
You get:
  - item : the new evidence.  item.body (text), item.provenance (STRUCTURED,
           trustworthy channel), item.era.  NOTE: item.tag is empty at runtime.
  - view : a READ-ONLY snapshot of the current belief state. You can read claims,
           cell states, the domain of competence, and declared absences. You
           CANNOT write to it. The only way to change the belief state is to
           return Deltas.

You return an IngestResult:
  - deltas    : a list of Delta objects (your proposed changes). See the vocabulary
                in groundtruth/deltas.py. Anything not in that vocabulary is rejected.
  - rationale : a short string explaining your decision (logged, good for debugging)
  - confidence: your confidence in this decision, 0..1
  - ood_flag  : True if this evidence falls OUTSIDE what the model represents

Run  `python selfcheck.py`  to test against the practice sandbox.
"""
from groundtruth.deltas import Delta, no_op
from groundtruth.ingest import EvidenceItem, IngestResult
from groundtruth.model import GraphView


def ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    # ---- starter: does nothing. Replace with your reasoning. ----
    #
    # Example of proposing a change (only through a Delta, never by writing to view):
    #   claim = view.get_claim("C3c")
    #   if claim is not None:
    #       return IngestResult(
    #           deltas=[Delta("revise_confidence", item.id,
    #                         {"claim_id": "C3c", "new_confidence": 0.4})],
    #           rationale="strong, replicated contradiction",
    #           confidence=0.8, ood_flag=False)
    #
    return IngestResult(deltas=[no_op(item.id)], rationale="starter no-op", confidence=0.5, ood_flag=False)
