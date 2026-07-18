# IMPROVEMENTS — raising the ceiling past edge cases

We have a robust, fully-passing baseline. The question is what separates a
*winning* submission from a merely-correct one. It is **not more keyword edge
cases** — that has sharp diminishing returns and is fragile against wording the
hidden set will use that we cannot enumerate.

**This is a retrospective finding, not a hypothesis.** Two structural fixes each
closed a whole *class* of misses that no keyword list would have caught reliably:
1. the terminal+source-cue **backward detector** (caught reprogramming phrased
   with no reversion keyword);
2. the **(from→to) direction extractor** (fixed forward-differentiation phrased
   without the word "differentiate" being misread as a reprogramming
   contradiction — a fabricated hit on the 40-pt axis, surfaced by the paraphrase
   harness).
The keyword broadenings done alongside these were worth far less.

**But read the second one as a cautionary tale, not a victory.** Its first version
replaced the `"differentiat"` crutch with a *word-order* crutch, and thereby
introduced a **worse** bug: a strong replicated reprogramming result that names the
destination first ("PSC colonies emerged after Fibroblast cells received defined
factors") was read as forward and silently dropped — a false negative on the 40-pt
axis, where the code it replaced was correct. It shipped green: the paraphrase
harness passed 12/12, because the same author wrote the fix and its tests and only
imagined one of the two failure directions. **Two lessons, both now load-bearing:**
- **A structural fix is not automatically a better fix.** Swapping one lexical
  crutch for another is lateral movement. Ask what the new crutch assumes (here:
  English subject-first word order) and whether the *default* it implies is safe.
- **Green from a suite you wrote alongside the fix is not evidence.** Adversarial
  probes must attack **both** directions of a rule, and known holes must be
  recorded as visible `XFAIL`s (see `tests/direction_probe.py` N8) rather than
  quietly omitted — an unrecorded hole is how the first one survived.

---

## The architectural tension, resolved

`ARCHITECTURE.md` correctly argues that for *this* closed, deterministic domain,
architecture **A (pure symbolic)** is near-optimal and adding an LLM (toward **E**)
increases risk for little gain. That must not be read as "migrate toward E."

**Name it explicitly: the highest-ROI work (structural classification) is a
*within-A* improvement.** It needs no Bayesian core and no LLM. It is orthogonal
to the A-vs-E debate. Do not let E's gravity provoke a rewrite the rubric will not
pay for.

---

## The residual ceiling is EXTRACTION, not classification

Structure can only decide *once you know which states and what direction*. That
step is still lexical — but the point of structural work is that it **moves the
lexical dependency from the phenomenon (an unbounded vocabulary) to entity +
direction (a small, stable one)**:
- **Entities:** proven not to be name-coupled — the renamed-seed harness is 12/12
  identical. (Residual gap: `find_states` is CamelCase-only, so lowercase
  multi-word entity phrases still lean on `_SOURCE_KW`.)
- **Direction:** resolved by `transition_direction` from *positive evidence only* —
  an origin cue (`"produced from <state>"`) or a transition connective linking the
  pair (`"gave rise to"`, `"into"`, `"toward"`) — then decided by **potency
  comparison**, never by the `"differentiat"` substring and **never by bare word
  order**. Grounded in the graph's own law: C1 says transitions do not increase
  potency, and `potency_level` is inverted, so a destination of *lower*
  potency_level is the C1-violating (newsworthy) reading. The two directions are
  asymmetric — a missed reprogramming is a false negative on the biggest axis,
  while source→terminal is already near-certain under C5 and is never news — so
  **forward must be positively evidenced and anything unresolved defaults to
  backward.**
  *Known residual (tracked, `direction_probe.py` N8):* a genuinely-forward result
  using an unrecognized connective and omitting "differentiat" defaults backward
  and is revised spuriously. That is the accepted price of the asymmetry, and it is
  the less-harmful error — but it is real, and it is the sharpest argument in this
  document for eventually not hand-parsing direction at all (Tier 2.4).

The honest framing for `DESIGN.md`: we do not eliminate the lexical step, we
*shrink its surface area to the smallest stable vocabulary* and make the decision
structural from there.

---

## Tier 1 — highest ROI (all within-A)

### 1.1 Structural classification (OOD precision + revision direction)
Drive in/out-of-model and forward/backward from the **graph** — potency delta,
lineage relationship, the `topological_assumption` — using text only to extract
*which* states and *what direction*. Keep pushing brittleness out of the
phenomenon vocabulary into entity+direction. **Status: backward detector and
direction extractor done; continue as harnesses expose gaps.**
**Risk:** low. **Effort:** medium. Keep keyword paths as fallback.

### 1.2 Calibration — reframe, do NOT rewrite  (DEMOTED)
The Bayesian rewrite buys **defensibility, not points, at real regression risk.**
The update is already additive in log-odds — `logit(post) = logit(prior) + LLR` —
so it is Bayesian *in form*, and prior-aware for free (verified: the same evidence
moves a 0.55 claim ~0.48 in probability but a 0.97 claim only ~0.31, because
log-odds space compresses near the ceiling). Reframing `2.8·S` as a sum of
per-dimension log-likelihood-ratios is the same function with a nicer derivation.
**Action:** describe `S` as an LLR pool in `DESIGN.md`; leave the engine alone.
**Risk of rewriting:** medium (threatens the green trajectory probe). **Do not.**

### 1.3 Sharpen `DESIGN.md`  (pure upside — do first)
Judges read it and reward "structure and instincts." Make it crisp: the
extraction/decision firewall separation, the log-odds (LLR-pool) calibration, the
structural OOD + direction discriminator, and *why* each resists a named failure
mode (anchor / flip-flop / trust-body / flag-all). **Point it at
`ARCHITECTURE.md`'s scope-nuance section** — arguing "A is near-optimal here, and
here is the exact condition under which that flips" reads as better judgment than
reaching for the impressive option. That judgment is the recruiting signal.
**Risk:** none. **Effort:** low.

---

## Tier 2 — real, but gated or higher-effort

### 2.1 Neural extraction with a deterministic fallback  (architecture signal)
Mirrors CORTEX's real system (LLM extraction → symbolic decision) and removes the
lexical dependency entirely. **Only if a model endpoint is actually provided**,
and only behind: temperature 0, schema-constrained output, and the current
rule-based classifier as fallback. The LLM only *extracts a typed frame*; it never
decides a mutation. See `ARCHITECTURE.md` (option E) for the full contract.
**Do not build speculatively.**

### 2.2 Richer scoped revision & rationale quality
"Narrowing beats deleting" is rewarded; make the complement-claim update magnitude
principled (tie to the same evidence weight) and rationales state the
provenance-based reason. Low risk, low effort, incremental.

---

## Tier 3 — testing discipline (this is the new source of signal)
Hand-written synonym probes are saturated (8 suites, all green). The generalization
harnesses replace guessing the hidden vocabulary with *measuring* coupling:
- **`tests/paraphrase_probe.py`** — re-word each hard item; verdict must not
  change. Includes the direction pair (forward vs backward, same entities). A
  failure localizes extraction brittleness.
- **`tests/renamed_seed_probe.py`** — rename entities to arbitrary tokens; verdict
  and trajectory must not change. Catches name-coupling.
Prefer a **structural** fix over a longer keyword list when a probe fails.

---

## What NOT to do
- Do not grow keyword lists as the primary strategy — fragile, low ceiling.
- Do not do the Bayesian rewrite — reframe in prose instead.
- Do not add an LLM path without a provided endpoint + deterministic fallback.
- Do not chase exact confidence numbers — the axis grades shape.
- Do not let any change touch the firewall guarantee (no body-derived mutation).

## Sequencing for the remaining time
1. **Sharpen `DESIGN.md`** (1.3) — pure upside; point it at the scope-nuance section.
2. **Run the generalization harnesses** (Tier 3) — cheap; tells you where real
   brittleness is instead of guessing.
3. **Structural fixes targeted at whatever the harnesses expose** (1.1).
4. Skip the Bayesian rewrite. Skip the LLM tier unless an endpoint materializes.
