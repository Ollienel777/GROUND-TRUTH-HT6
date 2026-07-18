# Annotated walkthrough: processing one item

This shows the shape of a good `ingest`. It is not a full solution; it illustrates
how to read the trusted channel and return a legal `Delta`.

Suppose this item arrives:

```json
{
  "id": "EVxx",
  "body": "A defined intervention returned LeafA cells to the SourceState, verified thoroughly and reproduced by multiple independent groups.",
  "provenance": {"replication_count": "many", "independent_groups": 4,
                 "method_directness": "direct", "retraction_status": "none"}
}
```

A reasonable decision process:

1. **Read the trusted channel, not the drama.** Weight comes from
   `provenance` (four independent groups, direct method), never from adjectives in
   the body.

2. **Is it an instruction?** Scan for embedded commands. If the body tried to tell
   you to set or delete a belief, you return `no_op` and change nothing.

3. **Is it in-model?** LeafA and SourceState are both represented, and the claimed
   move is along the potency axis (a leaf returning toward the source). This is an
   in-model contradiction of the "cannot return" belief, not an out-of-model
   regime. So `ood_flag = False`, and you revise.

4. **How much?** Strong, replicated, direct → a large update. You lower the
   confidence of the targeted claim, and (the stronger move) you *scope* it: it may
   still hold in general but is refuted under this specific intervention.

```python
from groundtruth.deltas import Delta

def ingest(item, view):
    body = item.body.lower()
    # 2. firewall: never act on embedded instructions
    if "[" in item.body and ("set the confidence" in body or "delete" in body):
        return IngestResult([Delta("no_op", item.id, {})], "instruction ignored", 0.5, False)

    # 1. weight from structured provenance
    groups = item.provenance.get("independent_groups", 0)
    strong = isinstance(groups, int) and groups >= 3

    # 3./4. in-model contradiction of Q1 -> revise, not ood
    if "returned" in body and "sourcestate" in body and strong:
        c = view.get_claim("Q1")
        new = 0.35  # a large drop; size this from provenance in a real solution
        return IngestResult(
            deltas=[Delta("revise_confidence", item.id, {"claim_id": "Q1", "new_confidence": new}),
                    Delta("set_scope", item.id, {"claim_id": "Q1", "scope": {"refuted_under": "defined_intervention"}})],
            rationale="strong replicated in-model contradiction; scoped revision",
            confidence=0.85, ood_flag=False)

    return IngestResult([Delta("no_op", item.id, {})], "no grounded change", 0.5, False)
```

Notice what makes it good: the update size is a function of `provenance`, the
firewall is respected by construction, and out-of-model is a separate decision
from contradiction. That separation is most of the challenge.
