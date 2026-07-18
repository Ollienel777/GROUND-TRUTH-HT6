# ARCHITECTURE — design study for calibrated, manipulation-proof belief revision

> Purpose: weigh candidate architectures for the GROUND TRUTH problem and justify
> the recommended one. Written to be read cold by a teammate. This is a design
> reference, not a description of the current hackathon code — see `PLAN.md` for
> what is built today and `IMPROVEMENTS.md` for the migration path.

---

## The problem, stated architecture-first

Maintain a **knowledge graph of beliefs** (claims with confidence + provenance)
that stays correct as experimental results stream in one at a time. For each
result the system must:

- revise beliefs **in proportion to evidence strength** (calibration),
- **never** let untrusted text mutate the graph (firewall),
- tell a genuine **in-model contradiction** apart from an **out-of-model** result
  (OOD: a non-representable *regime* or an untracked *axis*),
- hold firm against **thin extraordinary claims** and resolve them cleanly.

LLMs may *propose* but must **never write** — the graph is the source of truth.

## The six properties any architecture is judged on

1. **Calibration** — updates proportional to evidence; correct trajectory shape.
2. **Firewall safety** — untrusted text *provably* cannot mutate state.
3. **OOD precision** — separate in-model contradiction from off-schema regime/axis.
4. **Skepticism** — resist thin extraordinary claims; resolve on later evidence.
5. **Determinism & auditability** — same input → same output; full provenance trail.
6. **Extraction robustness & scale** — handle open-ended language and large schemas.

---

## Candidate architectures (A–E)

### A. Pure symbolic / rule-based
Extraction by keywords/regex + graph lookups; decision by rules and a log-odds
update. **This is the current hackathon implementation.**
- **Strengths:** firewall is trivially safe (there is *no* text→mutation code
  path); fully deterministic and auditable; fast; zero cost/dependencies.
- **Weaknesses:** extraction is brittle to wording; does not scale beyond a
  hand-modeled domain; heavy per-domain engineering.
- **Verdict:** near-optimal for a *closed, small, fully-specified* domain; wrong
  for open-ended production input.

### B. End-to-end LLM proposes deltas, validator gates
The LLM reads the graph + item and emits proposed deltas; a symbolic validator
checks vocabulary/attribution/caps.
- **Strengths:** least engineering; flexible; strong extraction.
- **Weaknesses (fatal for this problem):**
  - **Calibration** is at the mercy of the model — poorly calibrated,
    tone-influenced, prone to "believe the latest." This is precisely the failure
    the task punishes.
  - **Firewall becomes only structural.** A validator can confirm a delta is
    well-formed and attributed, but **cannot distinguish a correct update from a
    manipulated one**. The safety cap does not save you.
  - Poor determinism/auditability.
- **Verdict:** the seductive trap — easiest to build, worst on the two properties
  that *define* the problem (calibration + firewall).

### C. LLM extraction → symbolic decision (neurosymbolic)
LLM (constrained decoding) parses the body into a typed frame; symbolic code does
firewall + calibration + OOD. Provenance magnitude comes from the structured
channel, never the LLM.
- **Strengths:** robust extraction across wording; firewall stays symbolic;
  auditable decision; scales to open text.
- **Weaknesses:** LLM nondeterminism (mitigable: temp 0, schema-constrained,
  fallback); extraction errors propagate; calibration still only a heuristic
  unless the decision layer is made probabilistic.
- **Verdict:** the right *skeleton*; becomes optimal once the decision core is
  genuinely probabilistic (→ E).

### D. Probabilistic graphical model / Bayesian core
Claims are random variables with dependencies; evidence updates via Bayes;
provenance → likelihood ratios; OOD via low posterior-predictive / model evidence.
- **Strengths:** calibration *is* Bayesian updating — this is the principled core
  for the 40-pt concern; dependencies (umbrella/children, complements) are native;
  scoped revision = conditioning; skepticism = a strong prior.
- **Weaknesses:** requires modeling structure + likelihoods; still needs an
  extractor to map text → which variable / what evidence; OOD-as-model-evidence
  needs a generative model.
- **Verdict:** the right *reasoning core*, but incomplete alone — it has no
  perception layer.

### E. Neurosymbolic + Bayesian core + symbolic firewall  ← RECOMMENDED
Compose the strengths: **neural perception → symbolic grounding → probabilistic
reasoning → symbolic control.** Each concern lives in the layer built for it.
- **Strengths:** strong on all six properties simultaneously; matches the
  production design CORTEX describes; the firewall is provable, not heuristic.
- **Weaknesses:** most moving parts; LLM layer needs determinism discipline and a
  fallback. Mitigated by making the neural layer *optional* over a rules default.
- **Verdict:** optimal for the real goal.

### Comparison

| Architecture | Calib. | Firewall | OOD | Skept. | Det./Audit | Extract/Scale |
|---|---|---|---|---|---|---|
| A. Pure symbolic (current) | ~ | ★★★ | ~ | ★★ | ★★★ | ✗ |
| B. End-to-end LLM + validator | ✗ | ★ | ~ | ✗ | ✗ | ★★★ |
| C. LLM extraction → symbolic | ★★ | ★★★ | ★★ | ★★ | ★★ | ★★★ |
| D. Bayesian core (+extractor) | ★★★ | ★★ | ★★ | ★★★ | ★★ | ~ |
| **E. Neurosymbolic + Bayesian + firewall** | ★★★ | ★★★ | ★★★ | ★★★ | ★★ | ★★★ |

*Reading the table:* no single architecture except E is strong on all six. The
insight is that A, C, D are each strongest in a **different layer** — which is why
the answer is their composition, not a choice among them. B is dominated on the
two defining properties and should be avoided despite being the easiest to ship.

---

## Recommended architecture E, in layers

**neural perception → symbolic grounding → probabilistic reasoning → symbolic control**

1. **Extraction (neural, *untrusted*).** LLM under constrained/structured decoding
   (JSON-schema function calling, temperature 0) turns each document into a typed
   `EvidenceFrame`: referenced entities linked to graph node IDs, the asserted
   transition/relation, the claimed phenomenon, and an extraction-faithfulness
   score. Optional self-consistency/ensemble. **Provenance is taken from the
   structured channel, never from the LLM.**

2. **Grounding & type-check (symbolic).** Resolve entities to real nodes; check
   whether the asserted transition is *expressible* under the schema's
   domain-of-competence and topological constraints. **OOD is decided here, and so
   is precision:** unresolvable property → axis OOD; off-schema transition (breaks
   the potency/topology rule) → regime OOD; expressible-but-contradictory →
   in-model. Exotic wording is irrelevant; only the structural move matters — this
   is how the near-miss trap is beaten.

3. **Calibrated updating (probabilistic).** A Bayesian / log-odds engine updates
   the targeted claim(s) using provenance as **likelihood evidence** (independent
   replication, method directness, retraction as likelihood ratios). Graph
   dependencies (umbrella/children, complements) propagate natively. Scoped
   revision = conditioning a claim on the failing regime. Skepticism = a strong
   prior: extraordinary departures demand correspondingly strong likelihood, so
   thin evidence produces ~zero movement and a *pending/quarantine* state rather
   than a write.

4. **Firewall & control (symbolic, *trusted*).** Every change is a typed,
   validated, attributed, magnitude-bounded Delta. The LLM has **no write path**.
   Full audit log on every change (what evidence, why, how much).

5. **Governance loop.** Pending claims resolve on later corroboration/retraction;
   OOD flags route to schema-extension proposals (human-in-the-loop or a separate
   proposer) — never auto-applied.

---

## The invariant that makes it manipulation-proof

> **Separate the trusted-magnitude channel from the untrusted-proposal channel,
> with a re-grounding validator between them.**

The LLM (untrusted) may only emit a *typed proposal* from a closed vocabulary;
that proposal is re-validated against ground truth; and the *magnitude* of any
belief change is computed by trusted code from structured provenance — never from
the LLM or the body text.

**Consequence:** a fully prompt-injected LLM can at worst *mislabel a transition*,
which the structural/type-check catches. It can never set a confidence, delete a
claim, or inflate provenance. This is layered defense — closed vocabulary →
re-grounding → trusted-magnitude → attribution/caps — and it is provable, not
heuristic. It is the single most important property of the design.

---

## Scope nuance — when a simpler design is correct

- **Open-ended input, large evolving schema, production trust needs → E**,
  unambiguously. It is the only design strong on all six axes and mirrors the
  real target system.
- **Closed, small, fully-modeled domain where determinism/auditability dominate
  (the hackathon) → A is genuinely near-optimal.** Adding an LLM there *increases*
  risk (nondeterminism, injection surface) for little gain.
- **Pragmatic bridge (recommended build order even for production): E with the
  extractor defaulting to rules and the LLM as an optional, fallback-guarded
  upgrade.** You keep the safe, deterministic core from day one; the neural layer
  is a drop-in that raises extraction recall without ever touching the firewall or
  calibration guarantees. This is also the exact migration path from the current
  code.

---

## What this means for the current implementation

The code today is architecture **A**, which is the correct skeleton: all
body-reading is confined to one perception seam, `extract(body, view) →
EvidenceFrame` (enforced by `seam_guard.py`), the decision core consumes only the
typed frame, and the firewall runs first on raw body *outside* the seam. That is the
E layering already — perception → grounding → probabilistic update → symbolic
control — with the perception layer in rules-mode. The two upgrades that sharpen the
**E** core are exactly the Tier-1 items in `IMPROVEMENTS.md`:

1. **Structural OOD** (grounding/type-check layer) instead of lexical keywords.
2. **Probabilistic log-odds calibration** instead of a tuned heuristic.

The neural extraction layer (Tier 2) is now a genuine drop-in rather than a rewrite:
because extraction is one seam emitting a typed frame, an LLM can replace `extract`
by emitting the same `EvidenceFrame`, with the rules path as the deterministic
fallback — valuable only with a model endpoint and open-ended input. Reassuringly,
the hackathon path and the "build it for real" path point in the same direction.

**A caveat so the two do not get conflated:** the Tier-1 structural work is a
*within-A improvement*, not a step toward E. It needs no Bayesian core and no LLM;
it is orthogonal to the A-vs-E choice. E's gravity should not be allowed to
provoke a rewrite this domain will not pay for.

**Where the residual ceiling actually is — extraction, not classification.**
Structural reasoning can only decide *once you know which states and what
direction*. That step stays lexical. The value of the structural work is that it
**moves the lexical dependency from the phenomenon (an unbounded vocabulary) to
entity + direction (a small, stable one)** and makes the decision structural from
there. Two empirical results bound this:
- **Entities are not name-coupled** — the renamed-seed harness is identical under
  arbitrary renaming.
- **Direction is load-bearing** — the lateral-vs-reversion and forward-vs-backward
  calls turn on it. It is resolved from *positive evidence only* (an origin cue, a
  transition connective, or an active production verb) and decided by potency
  comparison against C1 — never from a single keyword and never from bare word order
  (that was a real regression; forward now requires evidence and ambiguity defaults
  backward). This is the
  smallest stable vocabulary we can reduce it to without a neural extractor; it is
  also where the next brittleness will surface (hunt it with the paraphrase
  harness), and it is the precise thing option E's extraction layer would remove.

---

## Technology notes (for the production build)

- **Extraction:** constrained decoding / JSON-schema function calling; entity
  linking to node IDs; temperature 0; self-consistency for robustness; a
  rules-based fallback path.
- **Reasoning core:** a PGM library or a hand-rolled log-odds engine; provenance
  dimensions as likelihood ratios; explicit priors for skepticism.
- **Graph + firewall:** a typed graph store (e.g. TypeDB / Datalog-style) where
  the *only* write path is the validated Delta API; provenance + audit on every
  claim.
- **Evaluation:** calibration metrics (Brier score, expected calibration error)
  on the revision axis; a standing adversarial-injection + OOD suite (we already
  have the seed of this in `tests/`).
