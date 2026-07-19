# DESIGN

A deterministic, rule-based `ingest` — no LLM, no network, so it cannot time out,
crash, or be talked into anything. **One principle governs the design: `provenance`
sets magnitude, `body` only classifies, and the two channels never cross.** Nothing is
keyed to names or IDs — every claim, state, axis, and regime resolves from the
read-only `view` and the domain declaration (verified: renaming every entity to
arbitrary tokens yields byte-identical verdicts). Pipeline: **firewall → strength →
parse → OOD → decision → magnitude.**

## Evidence weighting — a log-odds likelihood-ratio pool
```
S = (0.65·groups + 0.35·replications) · directness · effect_strength ∈ [0,1]
logit(posterior) = logit(prior) ∓ 2.8·S
```
This is evidence accumulation in log-odds — each provenance dimension contributes to a
pooled likelihood ratio; Bayesian *in form*. Honestly: the constants (`0.65/0.35`, the
`2.8` scale) are a tuning surface — we moved the heuristic into an LR table, we did not
eliminate it. What is *not* tuned is the trajectory **shape** the rubric grades, which
falls out of log-odds itself: **prior-aware** (the same evidence moves a contested 0.55
claim far more than a near-certain 0.97 — log-odds compresses near the ceiling),
**near-zero on noise** (sub-ε moves collapse to `no_op`), **never clamped** (2.8 sits
under the API's 3.0 cap). That is why we keep the pool rather than a full Bayesian net:
the shape is already right, and the constants are cheaper to defend than to re-derive.
Counts normalize via a word ladder (`few=2, several=4, many=6`) and saturate;
independence dominates as the least-gameable signal; `retracted` is a hard override. **No
number in `body` is ever read** — "250 laboratories" against `independent_groups: 1` is
defeated by construction, not detection. Revision **narrows, never deletes**: it targets
the scoped *child* claim (`method_class → mechanism_class`), not the umbrella; adds
`set_scope {refuted_under}`; raises the contested complement; and on strong evidence
promotes the matching declared absence to an edge — one item, a multi-claim update.

## Skepticism is security work, not just calibration
The structured provenance is *adversary-authored* — schema-valid, not honest. Computing
magnitude from it deterministically doesn't make it trustworthy; it confines the
adversary to a narrow, typed, auditable interface instead of free text, and the
skepticism prior is what defends *that* interface. It keys on **independence, never
recognition**: a *single-source* contradiction — not independently reproduced, however
high its internal `replication_count` — is *held* (`hold_pending`) regardless of the
target's confidence, then resolved (dropped on a structured retraction, promoted only on
independent corroboration). So the fabricated false-alarm is caught for *thin provenance*,
not recognized from training data. The honest limit: the schema has no source identity,
so a *maxed* fabrication (many claimed independent groups) is undetectable by
construction — which is exactly why such a trap must be, and is, thin.

## Classification is structural, not lexical
Text names only *which states* and *what direction*; the graph decides the rest. All
body-reading is confined to one seam, `extract(body, view) → EvidenceFrame`; a build-
failing test enforces that nothing downstream reads the text.
- **OOD** is precision-first and defaults in-model: a potency-*changing* move is on a
  modeled axis (in-model — including the exotic-sounding near-miss); a
  potency-*preserving* jump between distinct identities is `lateral_somatic_conversion`;
  an untracked property matches an excluded axis. Flagging is never a catch-all.
- **Direction** is decided by potency against the graph's own law (C1: transitions don't
  increase potency; `potency_level` is inverted, so a *lower*-potency destination is the
  law-violating, newsworthy reading). The defaults are asymmetric because the errors are:
  source→terminal is never news (C5), a missed reprogramming is a false negative on the
  biggest axis — so **forward requires positive evidence** (an origin cue or a transition
  connective), and anything unresolved defaults to backward. Never inferred from bare word
  order.
- **Event scope** (NegEx/ConText-style, in the seam): a reversion cue counts only if
  actually *asserted*. Negation ("did *not* revert"), modality ("*if* cells *could*…"),
  static predication ("*is* more potent than"), and cross-clause distractors are each
  voided, scoped per clause with an *asserted-wins* rule. A failed or absent reversion is
  evidence *for* irreversibility, never against it.

**What each choice resists:** *trust-the-body* → provenance-only magnitude; *flip-flop* →
bounded LR pool + ε gate; *anchor* → thin evidence is held, not explained away, and
resolves later; *flag-everything* → structural in-model default.

## Firewall
State changes **only** through returned `Delta`s, and the wall is *structural*: no code
path leads from body text to a payload value, and magnitude comes solely from provenance —
so with no supporting provenance the move is exactly zero. The injection gate (embedded
directives → `no_op`; unicode/zero-width/letter-spacing normalized; scientific "override a
barrier" allowed, "override the confidence" blocked) is defense-in-depth *on top* of that
wall, not the wall itself. We never bet on the API cap — an emitted-but-rejected mutation
still counts — so an injection emits `no_op` only; any unexpected error also degrades to
`no_op`. An independent red-team (not the authors, ~90 attacks) produced no body-only
mutation, consistent with the guarantee being structural.

## Known limits & architecture
Extraction — *which states, what direction* — is still lexical, shrunk to the smallest
stable vocabulary and isolated behind the seam. A sufficiently oblique negation, or a
source named in an oblique non-`from` phrase, can still slip; the deliberately
less-harmful hole is kept visible as an `XFAIL` (`direction_probe.py` N8). That is the
price of rules-mode perception and the exact ceiling a neural extractor would lift.

This is symbolic **architecture A**, laid out in the neurosymbolic order (perception →
grounding → probabilistic update → symbolic control) with perception in rules-mode. For a
closed, fixed domain that is the correct choice, not a compromise: an LLM would buy
extraction recall at the cost of determinism and a new injection surface — and here it is
moot anyway, since the organizers confirmed there is no model endpoint and `ingest` runs
in-process under a stdlib-only rule. Because extraction is one seam emitting a typed frame,
a neural extractor remains a clean drop-in should that ever change. `ARCHITECTURE.md` has
the full A–E comparison and why an LLM-proposes-deltas design fails the two properties —
calibration and firewall — that define this problem.
