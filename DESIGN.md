# DESIGN

A deterministic, rule-based `ingest` (no LLM, no network) structured as a strict
pipeline: **firewall → strength → parse → OOD → decision → magnitude**. One
principle governs the whole design: **`provenance` sets magnitude; `body` only
classifies.** The two channels never cross, and nothing is keyed to the practice
names — every claim, state, axis, and regime is resolved from the read-only
`view` and the domain declaration, so the same code runs on the hidden graph.

## Evidence-weighting model

I read a single scalar strength `S ∈ [0,1]` from the structured channel only:

```
S = (0.65·groups + 0.35·replications) · directness · effect_strength
```

`groups`/`replications` are normalized through a word→number ladder
(`few=2, several=4, many=6`, ints pass through) and saturate at 6; independent
replication dominates because it is the least gameable signal. `method_directness`
and `effect_strength` are multipliers; `retraction_status = retracted` is a hard
override. Adjectives, self-asserted counts, and any number appearing in `body` are
never read — a body claiming "100 labs" while `independent_groups: 1` is defeated
by construction.

**Update size** is proportional to `S` in **log-odds** space, the graph's native
representation: `Δlogit = 2.8·S`, direction `−` for contradiction, `+` for
support. `new = sigmoid(logit(prior) ± Δlogit)`. The 2.8 ceiling sits under the
API's 3.0 cap so a revision is never clamped. A sub-`ε` move (`|Δlogit| < 0.15`)
collapses to `no_op`, which gives "near-zero on noise" for free. Result: large
moves on strong replicated evidence, small on moderate, none on weak — the
trajectory *shape* the rubric grades, not fitted numbers.

**Calibration extras.** Revision targets the **scoped child** claim (routing
`method_class → mechanism_class`, e.g. `defined_factor_perturbation → C3c`), never
the umbrella — the framework recomputes `umbrella = min(children)` itself. I also
`set_scope {refuted_under: <mechanism>}` (narrow, don't delete), raise the
contested complement claim (evidence for reversion supports "retains full
potential"), and, on strong evidence, promote the matching declared absence to an
edge. Together these produce a multi-claim, provenance-shaped update from one item.

**Skepticism.** A single-source, unreplicated contradiction (`is_thin`) is never
allowed to drive a revision, *regardless of the claim's current confidence* — it
is held via `hold_pending`. When a later item retracts it or reports failure to
replicate, the pending is dropped cleanly by a deterministic key; when a later
well-powered study confirms it, the held claim resolves into a real revision. This
keys off provenance thinness, not on recognizing any specific result, so the
fabricated false-alarm gets no help from prior knowledge.

## Firewall enforcement

The belief state changes **only** through the returned `Delta` list, and I enforce
that at three layers:

1. **No mutation is ever derived from text.** Magnitude comes exclusively from
   `provenance`; `body` is used only to match entities/transitions. There is no
   code path from a body string to a payload value.
2. **Explicit injection gate (Stage 0, first).** Before anything else, bodies
   carrying embedded directives (imperative KB commands, or bracketed
   `[…]`/`{…}` notes addressing the processor) return `no_op` and nothing else.
3. **Never bet on the safety cap.** The harness records an *attempted* mutation
   the instant a mutating op is emitted, even if the API rejects it. So an
   injection item emits `no_op` only — I never emit a revision hoping the cap
   clamps it.

Out-of-distribution detection runs **before** any revision and defaults to
in-model (precision-first): only a match against `axes_excluded`
(→ `propose_axis`) or `regimes_not_modeled` (→ `propose_regime`) flags OOD. The
discriminator is the topological rule — a move that changes potency is on the
modeled axis (in-model, even the near-miss reversion within a lineage), whereas a
potency-preserving jump between distinct identities is `lateral_somatic_conversion`
(out-of-model). Flagging is therefore never a catch-all.

The whole pipeline is wrapped so any unexpected error degrades to a `no_op`,
keeping the run deterministic and crash-free.
