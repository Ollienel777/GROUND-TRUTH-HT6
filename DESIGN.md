# DESIGN

A deterministic, rule-based `ingest` — no LLM, no network, so it cannot time out,
crash, or be talked into anything. One principle governs the design: **`provenance`
sets magnitude; `body` only classifies; the channels never cross.** Nothing is keyed
to names or IDs — every claim, state, axis and regime resolves from the read-only
`view` and the domain declaration (verified: renaming every entity to arbitrary
tokens yields identical verdicts).

Pipeline: **firewall → strength → parse → OOD → decision → magnitude.**

## Evidence weighting: a log-likelihood-ratio pool

```
S = (0.65·groups + 0.35·replications) · directness · effect_strength    ∈ [0,1]
Δlogit = 2.8·S          new = sigmoid(logit(prior) ∓ Δlogit)
```

Read this as **evidence accumulation in log-odds**, the graph's native space: each
provenance dimension contributes weight to a pooled log-likelihood ratio, and the
update is `logit(posterior) = logit(prior) + LLR` — Bayesian in *form*. To be honest
about what that does and doesn't buy: the per-dimension weights (the 0.65/0.35 split,
the 2.8 scale) are still a tuning surface — we moved the heuristic into the
likelihood-ratio table, we did not eliminate it. What is *not* tuned is the trajectory
**shape** the rubric grades, which is a property of log-odds accumulation rather than of
the constants. Three such properties fall out: **prior-aware** (the same evidence moves
a contested 0.55 claim ≈0.48 in probability but a near-certain 0.97 only ≈0.31 —
log-odds compresses near the ceiling); **near-zero on noise** (sub-ε moves,
`|Δlogit| < 0.15`, collapse to `no_op`); **never clamped** (2.8 sits under the API's
3.0 cap). This is why we keep the pool and do *not* rewrite it into a full Bayesian
network: the shape is already right, and the constants are cheaper to defend than to
re-derive.

`groups`/`replications` normalize via a word→number ladder (`few=2, several=4,
many=6`) and saturate; independent replication dominates as the least gameable
dimension. `retracted` is a hard override. **No number in `body` is ever read** — a
body asserting "250 laboratories" against `independent_groups: 1` is defeated by
construction, not by detection.

**Narrow, don't delete.** Revision targets the scoped *child* claim
(`method_class → mechanism_class`), never the umbrella (recomputed as `min(children)`).
We also `set_scope {refuted_under}`, raise the contested complement, and on strong
evidence promote the matching declared absence to an edge — one item, a multi-claim,
provenance-shaped update.

**Skepticism is security work, not just calibration.** The structured provenance is
*adversary-authored* — schema-valid, not honest. Computing magnitude from it
deterministically does not make it trustworthy; it only confines the adversary to a
narrow, typed, auditable interface instead of free text, and the skepticism prior is
what defends *that* interface. It keys off **independence, never recognition**: a
*single-source* contradiction — one not independently reproduced, no matter how high
its internal `replication_count` — is *held* (`hold_pending`) regardless of the
target's confidence, then resolved: dropped on a structured retraction, promoted to a
real revision only on independent corroboration (the boundary is one independent group
→ two). The announced fabricated false alarm therefore gets no help from prior
knowledge — it is caught because its provenance is *thin*, not because the text is
recognized. And the honest limit of the defense: the schema carries no source
identity, so a *maxed* fabrication — many claimed independent groups — is undetectable
by construction. That is precisely why the trap must be, and is, thin-provenance; we
defend the attack the interface can express and say plainly where it cannot.

## Classification is structural, not lexical

Text identifies only *which states* and *what direction*; the graph decides the rest.
All body-reading is confined to one seam, `extract(body, view) → EvidenceFrame` — a
typed bundle of classification signals, never magnitude or a command; the decision core
consumes the frame, never the text. A structural test fails the build if any keyword is
read outside it.

- **OOD** is precision-first and defaults in-model. A potency-*changing* move is on a
  modeled axis — in-model, including the exotic-sounding near-miss. A
  potency-*preserving* jump between distinct identities is
  `lateral_somatic_conversion`; an untracked property matches `axes_excluded`.
  Flagging is never a catch-all.
- **Direction** is decided by potency comparison against the graph's own law: C1 says
  transitions do not increase potency, and `potency_level` is inverted, so a
  destination of *lower* potency is the C1-violating — newsworthy — reading. **The
  directions are asymmetric, so the defaults are too:** source→terminal is already
  near-certain under C5 and is never news, whereas a missed reprogramming is a false
  negative on the largest axis. So **forward requires positive evidence** (an origin
  cue, or a transition connective linking the pair); anything unresolved defaults to
  backward. Direction is never inferred from word order.

**What each choice resists:** *trust-the-body* → provenance-only magnitude;
*flip-flop* → bounded LLR pool + ε gate; *anchor* → thin evidence is held rather than
explained away, and resolves later; *flag-everything* → structural in-model default.

## Firewall

State changes **only** through the returned `Delta` list. The seam above is the first
guarantee — no code path leads from body text to a payload value. Two more: the
**injection gate runs first**, so bodies with embedded directives return `no_op` and
nothing else (unicode/zero-width normalized, letter-spacing defeated); and we **never
bet on the cap** — the harness records an *attempted* mutation the moment a mutating op
is emitted, even if the API rejects it, so an injection emits `no_op` only. Any
unexpected error also degrades to `no_op`.

## Known limits

Classification is structural; **extraction** (which states, what direction) is still
lexical — shrunk to the smallest stable vocabulary, not eliminated, and now isolated
behind the single `extract` seam. That is where the residual brittleness lives, and
one hole is knowingly accepted and kept visible as an `XFAIL` rather than omitted
(`direction_probe.py` N8: a forward result that puts the source in an oblique phrase —
"arose in cultures *seeded with* PSC" — defaults backward, deliberately the
less-harmful error).

**On architecture:** this *is* the neurosymbolic design — perception → grounding →
probabilistic update → symbolic control — with perception deliberately in rules-mode,
since for a closed, fully-modeled domain an LLM buys recall at the cost of determinism
and an injection surface. Because extraction is one seam emitting a typed frame, that
call is reversible: an LLM is a drop-in (same frame, rules as fallback) once an
endpoint and open-ended input justify it. `ARCHITECTURE.md` has the full comparison —
including why the LLM-proposes-deltas shortcut fails on the two properties that define
this problem — and the condition under which the neural layer earns its place.
