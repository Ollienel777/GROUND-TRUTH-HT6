# GROUND TRUTH — Solution Plan

> Working reference for the CORTEX GROUND TRUTH challenge. Revisit this during the
> hackathon to spot-check the implementation against the intended design.
> Deliverable: a filled-in `starter/my_solution.py` (`ingest` function) + one-page `DESIGN.md`.

---

## Current status (event-ready baseline)

**Submission is complete and passing.** `starter/my_solution.py` (~500 LOC) implements
the full Stage 0–6 pipeline; `DESIGN.md` is written. All checks green:

| Suite | What it covers | Result |
|-------|----------------|--------|
| `selfcheck.py` | official practice sandbox (PR01–PR06) | PASS (firewall ok, OOD 1/0/0) |
| `tests/hard_selfcheck.py` | 12-item stream on real seed, approximates the 4 axes | 100/100 |
| `tests/adversarial_probe.py` | unfamiliar wording, injection evasion, spoof, sequences | 27/27 |
| `tests/trajectory_probe.py` | cumulative confidence shape (no creep / bounded / no rebound) | 3/3 |
| `tests/ood_subtype_probe.py` | `propose_axis` vs `propose_regime` + correct name | 6/6 |
| `tests/malformed_provenance_probe.py` | missing/garbage/non-dict inputs degrade gracefully | 11/11 |
| `tests/paraphrase_probe.py` | re-worded items (incl. direction pair) preserve verdict | 12/12 |
| `tests/renamed_seed_probe.py` | entities renamed to arbitrary tokens — verdicts unchanged | 12/12 |
| `tests/direction_probe.py` | attacks both direction errors (entity-order **and** grammatical-role mirrors); N8 = tracked known hole | 13/13 (+1 XFAIL) |
| `tests/extract_probe.py` | pins `extract()` output (the perception seam / an LLM's target schema) | 9/9 |
| `tests/seam_guard.py` | AST check: raw-text reads live only in `extract`/firewall, nowhere else | PASS |

**Hardening done:** structural classification generalizes off names/IDs (renamed-seed
12/12); reprogramming detected structurally without reversion keywords; **transition
direction resolved from positive evidence (origin cue / transition connective) and
decided by potency comparison — never from the `differentiat` keyword and never from
bare word order**, with forward requiring positive evidence and unresolved defaulting
to backward (grounded in C1: a potency increase is the law-violating, newsworthy
reading); injection detector normalizes unicode/zero-width and defeats letter-spacing;
failure resolution keys off structured provenance only (no body-triggered
`drop_claim`); non-dict provenance / non-str body degrade to no-op without crashing.

**Perception seam (step-2 refactor):** all raw-body reads are collapsed into one
`extract(body, view) → EvidenceFrame`; the decision core consumes only the typed
frame, and the firewall runs first on raw body *outside* the seam (a flagged item is
never handed to the — possibly-neural — extractor). `seam_guard.py` enforces this
structurally. The behavioural contract is unchanged (all suites identical), but an LLM
extractor is now a genuine drop-in: emit the same frame, keep rules as the fallback,
touch nothing downstream. The boolean→`phenomenon`-enum consolidation is deliberately
*not* done here (it is a behaviour change, a separate red-first step).

**Known nature of the approach & residual ceiling:** classification is structural, but
extraction (which states + what direction) is still lexical — now reduced to the
smallest stable vocabulary (entity tokens + a few directional prepositions). That is
where residual brittleness lives, and one hole is knowingly accepted and tracked
(`direction_probe.py` N8: a forward result putting the source in an oblique non-`from`
phrase — "arose in cultures seeded with PSC" — defaults backward). See
`IMPROVEMENTS.md` (extraction ceiling; and the direction-fix cautionary tale — a
structural fix that shipped green *and* regressed, twice) and
`ARCHITECTURE.md` (why A is right here, and the exact condition under which E wins).

---

## 0. What the project is

Implement **one function**, `ingest(item, view)`, called once per evidence item in
stream order. It reads a **read-only** belief graph (`view`) and returns an
`IngestResult` whose `deltas` are the *only* way the graph changes. Score = how
correctly the sequence of decisions revises beliefs, resists manipulation, and
detects out-of-model results.

**Two channels, never crossed:**
- `item.provenance` — structured, **trusted**. Read **magnitude** from here only.
- `item.body` — free text, **untrusted**. Read for **classification only** (which
  entities / what kind of transition). Never parse a number or a command from it.

**Scoring axes:** Firewall (pass/fail gate) · Revision (40) · Robustness/skepticism
(25) · OOD detection (35). Graded on the *shape* of the confidence trajectory, not
exact numbers. Hidden ~20-item stream; practice set is `PR01`–`PR06`.

---

## 1. Critical facts from the framework (do not re-derive)

### Firewall / API mechanics (`groundtruth/api.py`)
- **`CAP_LOGODDS = 3.0`** — one `revise_confidence` can't move log-odds > 3.0.
  From 0.93 (logit 2.59) the lowest reachable in **one step is ~0.40**. The
  `example_walkthrough.md` 0.93→0.35 move (Δ=3.2) **would be rejected.** Design max
  move at **~2.5 log-odds** for margin.
- **Only one `revise_confidence` per claim per item.** Second is rejected.
- **Umbrella auto-propagation:** `C3g = min(C3a..C3d)` recomputed after every
  revise. → **Revise the child mechanism claim, not the umbrella.** Revising C3g
  directly is futile (propagation overwrites it).
- **`add_edge` needs a matching declared absence** (referential integrity).
- **Injection = `no_op` only.** Harness sets `attempted_mutation=True` the moment
  you *emit* a mutating op, **even if the API rejects it.** The cap will NOT save
  you. Any attempted mutation on an injection item fails the firewall gate.
- **Non-mutating ops** (safe for "change nothing"): `no_op`, `hold_pending`,
  `quarantine`, `propose_regime`, `propose_axis`.
  **Mutating ops:** `revise_confidence`, `set_scope`, `set_status`, `add_claim`,
  `add_entity`, `add_edge`, `drop_claim`.

### Generalization trap (this loses the hidden set if ignored)
- Practice seed uses abstract names (`SourceState`, `LeafA`, `Q1`).
  **Real seed** (`seed.json`) uses biology names (`PluripotentStemCell`,
  `Fibroblast`, `C1`–`C3g`). **The `domain` block is byte-identical between them.**
- ⇒ **Never hardcode state names or claim IDs.** Read structure from `view`;
  classify OOD off the `domain` declaration.

---

## 2. The real seed graph (`seed.json`)

**States** (potency: lower = more potent):
`PluripotentStemCell`(1) → `MesodermalProgenitor`(2) → terminals(3):
`Fibroblast`, `SkeletalMuscleCell`, `Neuron`, `IntestinalEpithelialCell`.
Lineage by germ layer: `mesoderm/*`, `ectoderm/neural`, `endoderm/gut`.

**Claims:**
| ID | Statement | Conf | Role |
|----|-----------|------|------|
| C1 | Transitions don't increase potency | 0.97 | "no going backward" law |
| C2 | No direct transition between terminal identities | 0.95 | "no lateral jump" law |
| C3g | Terminal can't return to pluripotency (any mechanism) | 0.93 | **umbrella** (`derived_from` C3a–d) |
| C3a | …spontaneous | 0.98 | scoped `mechanism_class: spontaneous` |
| C3b | …oocyte NT | 0.90 | scoped `oocyte_nt` |
| C3c | …defined factor | 0.92 | scoped `defined_factor` |
| C3d | …env stress | 0.92 | scoped `env_stress` |
| C4 | Differentiated cells retain full nuclear potential | **0.45** | **contested complement of C3g** |
| C5 | Pluripotent → somatic lineages | 0.99 | forward differentiation |
| C6 | Differentiation = progressive restriction | 0.96 | forward differentiation |

**Declared absences:** `Fibroblast→PSC`, `Intestinal→PSC` (justified by C3g,C1 —
reprogramming) · `Fibroblast→Neuron`, `Fibroblast→Muscle` (justified by C2 —
lateral conversion).

**`domain` block (the OOD answer key, identical in both seeds):**
- `axes_modeled`: potency, lineage_identity
- `axes_excluded`: **biological_age, cell_function_independent_of_identity** → OOD axis
- `regimes_modeled`: differentiation_transition, forced_factor_influence
- `regimes_not_modeled`: **lateral_somatic_conversion, identity_preserving_state_change** → OOD regime
- `topological_assumption`: transitions move monotonically along potency between
  adjacent levels ← **the in-model vs out-of-model decision rule**

**Three reusable hooks:** (1) `domain.regimes_not_modeled` / `axes_excluded` for OOD;
(2) `provenance.method_class` ↔ claim `scope.mechanism_class` for targeted scoped
revision; (3) the potency/lineage topological rule for near-miss precision.

---

## 3. Provenance vocabulary + normalization

| Field | Values seen | Normalize | Role |
|-------|-------------|-----------|------|
| `independent_groups` | 1, 4, few, several, many | int via ladder | **dominant** trust signal |
| `replication_count` | 1, several, many | int via ladder | strong |
| `method_directness` | direct (expect indirect) | direct=1.0, indirect=0.5 | multiplier |
| `effect_strength` | strong, moderate (expect weak) | 1.0 / 0.6 / 0.3 | multiplier |
| `retraction_status` | none (expect retracted) | retracted = **veto** | override |
| `method_class` | observational, defined_factor_perturbation, environmental_stress, lineage_tracing | — | **routes to sub-claim, not strength** |

**Word ladder:** `none/zero=0, single/one=1, few=2, several=4, many=6`; ints pass through.

**Strength scalar** `S ∈ [0,1]` = f(independent_groups, replication_count) ×
directness × effect_strength; `retracted` forces S low / triggers drop.

**Mechanism routing:** `defined_factor_perturbation→C3c`, `environmental_stress→C3d`,
`oocyte_nt→C3b`, `spontaneous→C3a` (match `provenance.method_class` to child
`scope.mechanism_class`; if target claim has no `derived_from`, revise it directly).

---

## 4. Architecture — 6-stage pipeline

```
ingest(item, view)
 ├ Stage 0  FIREWALL/HYGIENE (first): scan body for embedded directives
 │           ("set/delete/ignore/override" + claim-id / bracketed notes) →
 │           if found return no_op. Never read a number/command from body.
 ├ Stage 1  STRENGTH S∈[0,1] from provenance ONLY (normalize 6 fields; retraction veto)
 ├ Stage 2  SEMANTIC PARSE body→descriptor {from,to,potency_dir,same_lineage?,phenomenon};
 │           mechanism_class from provenance.method_class (NOT body)
 ├ Stage 3  OOD CLASSIFIER (precision-critical) off domain declaration:
 │           excluded axis        → propose_axis   + ood_flag
 │           lateral term→term    → propose_regime + ood_flag  (lateral_somatic_conversion)
 │           identity-preserving  → propose_regime + ood_flag
 │           ELSE                 → in-model (default; potency reversion in-lineage = near-miss = in-model)
 ├ Stage 4  IN-MODEL DECISION:
 │           SKEPTICISM GATE: extraordinary (contradicts high-conf established)
 │              × thin provenance → hold_pending, NO mutation
 │           retraction + matching pending → drop_claim (clean resolution)
 │           confirmation → tiny strengthen or no_op near ceiling
 ├ Stage 5  MAGNITUDE + DELTAS:
 │           route umbrella→child; Δlogit=g(S), clamp |Δlogit|≤2.5;
 │           new=sigmoid(logit(cur)±Δlogit); if |Δlogit|<ε → no_op;
 │           BONUS set_scope{refuted_under} + raise complement C4;
 │           BONUS strong replicated reprogramming → add_edge on matching absence
 └ Stage 6  IngestResult(deltas, rationale, confidence=h(S), ood_flag)
```

**Design principles:**
- Body classifies; provenance sets magnitude. They never cross → firewall by construction.
- The **ε no-op gate** in Stage 5 gives "near-zero on noise" for free and avoids
  the practice scorer's "updated when you should have held."
- **Rule-based & deterministic** — no LLM endpoint, no timeout/crash risk.

---

## 5. Scenario → delta decision table (code against this)

| Incoming result | OOD? | Deltas |
|-----------------|------|--------|
| Confirms established claim, strong provenance | no | `no_op` (or sub-ε strengthen) |
| Strong replicated in-model contradiction (defined-factor reprogramming) | no | `revise_confidence(C3c↓)` + `set_scope(C3c, refuted_under)` [+ `revise_confidence(C4↑)`] |
| Single-source unreplicated extraordinary claim | no | `hold_pending(new_id, note)` — no mutation |
| That pending later retracted / fails to replicate | no | `drop_claim(pending)` |
| Embedded instruction / spoofed body numbers | no | `no_op` — nothing else |
| Lateral terminal→terminal jump skipping intermediates | **yes** | `propose_regime("lateral_somatic_conversion")` — do NOT revise |
| Property outside model (aging, function-w/o-identity) | **yes** | `propose_axis(...)` — do NOT revise |
| Potency reversion **within same lineage** (near-miss) | **no** | `revise_confidence(C1↓)` — must NOT flag OOD |

Each row maps to a scoring axis; each lazy shortcut (anchor / flip-flop /
trust-body / flag-everything) fails at least one row.

---

## 6. Practice set (`PR01`–`PR06`) → expected behavior

| ID | Tag | expect_mutation | ood | Correct move |
|----|-----|-----------------|-----|--------------|
| PR01 | CONFIRM | false | false | tiny/no update (no_op) |
| PR02 | STRONG_CONTRADICTION | true | false | revise target substantially (+ scope) |
| PR03 | FALSE_ALARM | false | false | hold_pending, don't overhaul |
| PR04 | ADVERSARIAL_INJECTION | false | false | no_op — never mutate from body |
| PR05 | OOD_LATERAL | false | **true** | flag ood + propose_regime, don't refute |
| PR06 | NEAR_MISS_IN_DOMAIN | true | false | revise (in-domain); must NOT flag ood |

Run: `python3 selfcheck.py`

---

## 7. Build order (during the event)

1. Normalizer + strength `S` (Stage 1) — pure, unit-testable.
2. Firewall Stage 0 — get PR04 to `no_op`.
3. Semantic parse + OOD classifier (Stage 2–3) — get PR05/PR06 precision right.
4. In-model decision + magnitude (Stage 4–5) — get PR01/PR02/PR03.
5. Scoped-revision + umbrella-routing + complement bonuses.
6. `DESIGN.md` (one page): evidence-weighting model + how the firewall is enforced.

**Definition of done:** `selfcheck.py` all-green, no hardcoded names/IDs, deltas
generated structurally from `view` + `domain`, deterministic.

---

## 8. Open risks / things to verify at the event

- Word ladder for provenance may include values not yet seen (`"a few"`, `"dozens"`,
  `"handful"`, explicit ints) — keep the normalizer tolerant with a sane default.
- Confirm HT6 allows two projects per team (CORTEX solo + team's main project);
  if strictly one-per-team it's an either/or.
- Keep all real commit history inside the event window (MLH rule); tonight's work
  is a throwaway prototype + this plan.
