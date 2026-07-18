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
update is `logit(posterior) = logit(prior) + LLR` — Bayesian in form, not a fitted
curve. Three properties fall out rather than being tuned in: **prior-aware** (the same
evidence moves a contested 0.55 claim ≈0.48 in probability but a near-certain 0.97
only ≈0.31 — log-odds compresses near the ceiling); **near-zero on noise** (sub-ε
moves, `|Δlogit| < 0.15`, collapse to `no_op`); **never clamped** (2.8 sits under the
API's 3.0 cap).

`groups`/`replications` normalize via a word→number ladder (`few=2, several=4,
many=6`) and saturate; independent replication dominates as the least gameable
dimension. `retracted` is a hard override. **No number in `body` is ever read** — a
body asserting "250 laboratories" against `independent_groups: 1` is defeated by
construction, not by detection.

**Narrow, don't delete.** Revision targets the scoped *child* claim
(`method_class → mechanism_class`, e.g. `defined_factor_perturbation → C3c`), never
the umbrella — the framework recomputes `umbrella = min(children)` itself. We add
`set_scope {refuted_under}`, raise the contested complement, and on strong evidence
promote the matching declared absence to an edge: one item, a multi-claim,
provenance-shaped update.

**Skepticism** keys off provenance thinness, never recognition. A single-source,
unreplicated contradiction is *held* (`hold_pending`) regardless of the target's
confidence, then resolved — dropped on a structured retraction, promoted to a real
revision on corroboration. The fabricated false alarm gets no help from prior
knowledge.

## Classification is structural, not lexical

Text identifies only *which states* and *what direction*; the graph decides the rest.

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

State changes **only** through the returned `Delta` list, enforced at three layers:

1. **No text→mutation path exists.** Magnitude comes exclusively from `provenance`;
   `body` only matches entities. No code path leads from a body string to a payload.
2. **The injection gate runs first.** Bodies carrying embedded directives return
   `no_op` and nothing else (unicode/zero-width normalized, letter-spacing defeated).
3. **Never bet on the cap.** The harness records an *attempted* mutation the moment a
   mutating op is emitted, even if the API rejects it — so an injection emits `no_op`
   only. Any unexpected error also degrades to `no_op`.

## Known limits

Classification is structural; **extraction** (which states, what direction) is still
lexical — shrunk to the smallest stable vocabulary, not eliminated. That is where the
residual brittleness lives, and one hole is knowingly accepted and kept visible as an
`XFAIL` rather than omitted (`direction_probe.py` N8: forward phrasing with an
unrecognized connective defaults backward — deliberately the less-harmful error).

**On architecture:** this *is* the neurosymbolic design — extraction → grounding →
probabilistic update → symbolic control — with the extractor deliberately in
rules-mode, since for a closed, fully-modeled domain an LLM buys recall at the cost of
determinism and a new injection surface. The tempting shortcut — LLM proposes deltas,
validator gates them — fails on the two properties that *define* this problem:
calibration becomes model-dependent, and a validator can confirm a delta is
well-formed but never that it is unmanipulated. `ARCHITECTURE.md` has the full
comparison and the condition under which the neural layer earns its place.
