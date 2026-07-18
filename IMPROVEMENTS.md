# IMPROVEMENTS — raising the ceiling past edge cases

We have a robust, fully-passing baseline. The question now is what actually
*separates a winning submission from a merely-correct one*. Honest take: **it is
not more edge cases.** Every serious team passes the four capabilities and the
practice set. Keyword-list hardening has sharp diminishing returns and is
*fragile* — the hidden set will use wording we did not anticipate, and a longer
keyword list is a losing arms race against text we cannot see.

The differentiators below are structural. They are ordered by expected ROI for
this rubric (Firewall gate · Revision 40 · Skepticism 25 · OOD 35) and the
sponsor's stated goal: "the right structure and the right instincts."

---

## Tier 1 — highest ROI

### 1. Make OOD precision *structural*, not lexical  (OOD, 35 pts)
Today OOD leans on keyword lists for the "phenomenon." The precision trap (a
near-miss that reads exotic but is in-model) is best beaten by reasoning over the
**graph**, not the prose. Drive the decision from:
- the **potency delta** between the source/target states (a move along the
  modeled axis = in-model, regardless of how exotic the words are),
- the **lineage_identity** relationship (same-lineage potency move = in-model;
  equal-potency across identities = lateral = out-of-model),
- the **`topological_assumption`** ("monotonic, adjacent-level") as the literal rule.
Use text only to *extract which states/transition* are described; let structure
decide in/out-of-model. This shrinks reliance on unpredictable wording and
directly attacks the precision half of the 35-point axis.
**Risk:** low. **Effort:** medium. Keep keyword paths as fallback.

### 2. Principled calibration in log-odds  (Revision, 40 pts — the biggest axis)
Current update size is a heuristic `S → Δlogit`. Reframe as **evidence
accumulation**: each provenance dimension contributes a log-likelihood-ratio
weight, summed in log-odds, so the update is a Bayesian-style pool rather than a
tuned scalar. Two things this buys:
- **Prior-aware updates:** the same evidence should move a 0.55 claim more than a
  0.97 claim (there is more to move). Log-odds gives this for free; make sure our
  mapping actually reflects it.
- **Defensible trajectory shape:** the graders score the *shape*; a principled
  model produces the right shape without per-case tuning.
**Risk:** medium (don't regress the trajectory probe). **Effort:** medium.

### 3. Sharpen `DESIGN.md`  (indirect, but judges read it)
The rubric rewards "structure and instincts," and `DESIGN.md` is where we show
them. Make it crisp: the extraction/decision firewall separation, the
log-odds calibration model, the structural OOD discriminator, and *why* each
resists a specific failure mode (anchor / flip-flop / trust-body / flag-all).
**Risk:** none. **Effort:** low. **Do this regardless.**

---

## Tier 2 — real, but gated or higher-effort

### 4. Extraction/decision split with an LLM front-end  (architecture signal)
CORTEX's real system is "an LLM under constrained decoding for extraction, then
symbolic/probabilistic code for the decision." Mirroring that — **LLM parses the
body into a structured frame `{from, to, transition_type, phenomenon}`; our
symbolic firewall + calibration make the decision** — is the single strongest
"right structure" signal, and it removes the keyword brittleness entirely.
Constraints to respect:
- **Determinism** is required → temperature 0, and a **deterministic rule-based
  fallback** (our current classifier) when no endpoint is available or a call
  fails/times out. A crash scores the item as a no-op, so wrap defensively.
- The LLM only *extracts*; it must **never** decide a mutation. The firewall stays
  symbolic. (This is also the honest story for `DESIGN.md`.)
**Risk:** medium–high (endpoint availability unknown; must not break determinism).
**Effort:** high. **Do only if a model endpoint is provided.**

### 5. Richer scoped revision & propagation  (Revision bonus)
"Narrowing beats deleting" is explicitly rewarded. We set `refuted_under` and
raise the complement claim. Extend: scope by *condition* more precisely, keep the
umbrella/children consistent, and make the complement update magnitude principled
(tie it to the same evidence weight, not a fixed factor).
**Risk:** low. **Effort:** low–medium.

### 6. Confidence & rationale quality  (instinct signal)
`IngestResult.rationale`/`confidence` are logged and read. Make rationales state
the *provenance-based* reason ("3 independent groups, direct method → large
down; scoped to defined_factor"). Cheap credibility.
**Risk:** none. **Effort:** low.

---

## Tier 3 — keep doing, but with discipline
Edge-case probes (our 6 suites) are the **regression net**, not the source of new
points. Keep adding cases that probe *structural* blind spots (new potency/lineage
configurations, unseen provenance encodings of failure), not just new synonyms.
When a probe fails, prefer a **structural** fix over a longer keyword list.

---

## What NOT to do
- Do not keep growing keyword lists as the primary strategy — fragile, low ceiling.
- Do not chase exact confidence numbers — the axis grades shape, not values.
- Do not let any change touch the firewall guarantee (no body-derived mutation).
- Do not add an LLM path without a deterministic fallback and defensive guards.

## Suggested order for the remaining time
1. Sharpen `DESIGN.md` (Tier 1.3) — fast, pure upside.
2. Structural OOD precision (Tier 1.1) — attacks the 35-pt trap directly.
3. Principled log-odds calibration (Tier 1.2) — the 40-pt axis.
4. If an endpoint exists: LLM extraction with fallback (Tier 2.4).
5. Scoped-revision + rationale polish (Tier 2.5/2.6) as time allows.
