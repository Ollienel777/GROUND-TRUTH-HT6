# ONBOARDING — start here

Welcome. This is the one doc to read first. It orients you to the project, points
you at the right deeper doc for each question, tells the story of *why the code
looks the way it does*, and shows you how to run everything. Nothing here is a
duplicate of another doc — it's the map and the connective tissue.

---

## 1. What this project is (in three sentences)

GROUND TRUTH is a CORTEX BioSciences challenge. We implement **one function**,
`ingest(item, view)`, that reads a streaming sequence of experimental "results" and
decides how a **belief graph** (claims with confidence values) should change — if at
all. The whole game is doing that *well*: move beliefs in proportion to evidence
strength, never let untrusted text mutate the graph (the "firewall"), tell a real
contradiction apart from something outside the model, and resist thin extraordinary
claims. No biology background needed — read it as an abstract graph of states,
transitions, and claims.

We are graded by an automated scorer on a **hidden** ~20-item stream we never see,
across four axes: **firewall** (pass/fail gate), **revision** (40), **skepticism**
(25), **OOD detection** (35).

## 2. Reading order

| Read | For |
|------|-----|
| `README.md` | the challenge as the organizers framed it (start of the "what") |
| `WHAT_IS_TESTED.md` | the detailed spec of the four scored capabilities |
| `RULES.md` | eligibility, what we may edit, the endpoint clause (short) |
| **this file** | orientation, narrative, how to run, key decisions |
| `DESIGN.md` | the one-page submission artifact: how the solution weighs evidence + enforces the firewall |
| `ARCHITECTURE.md` | the design study — five candidate architectures (A–E), why we chose the one we did, and the exact condition under which that flips |
| `PLAN.md` | the solution plan, the live status table, and framework facts not to re-derive |
| `IMPROVEMENTS.md` | what raises the ceiling from here — and two cautionary tales worth reading before you touch the code |

If you read only two, read `WHAT_IS_TESTED.md` (what we're graded on) and the rest
of this file (how we do it and why).

## 3. Current status

**Complete and passing.** `starter/my_solution.py` implements the full pipeline;
`DESIGN.md` is written. Everything is committed; the tree is clean. All checks green:

- `selfcheck.py` (official practice sandbox) — PASS
- `tests/hard_selfcheck.py` (12-item stream on the real seed, approximates the 4 axes) — **100/100**
- 9 dev probe suites — all green (see §6)

So the baseline is solid. The active work is *raising the ceiling* (§8), not fixing
breakage.

---

## 4. How the code works

**You only edit `starter/my_solution.py`.** Everything under `groundtruth/` is the
framework and is off-limits (at judging our function runs against the official
framework + the hidden stream). Key framework files to *read* (not change):
`groundtruth/model.py` (the graph + the read-only `GraphView`), `groundtruth/deltas.py`
(the closed set of allowed changes), `groundtruth/api.py` (the firewall — the only
write path), `groundtruth/data/seed.json` (the starting graph).

### The one invariant that governs everything

> **`provenance` sets magnitude; `body` only classifies. The two channels never cross.**

Each incoming item has structured `provenance` (trusted: how many groups replicated
it, method directness, retraction status) and a free-text `body` (untrusted: can lie
or contain embedded "set this to certain" instructions). We read **magnitude only
from provenance** and use **body only to classify** (which states, what kind of
transition). Because no number or command ever flows from body text into a change,
the firewall holds *by construction*, not by detection. Internalize this — most of
the design falls out of it.

### The pipeline (all in `starter/my_solution.py`)

`ingest` (entry point, ~L499) wraps `_ingest` (~L506) in a try/except so nothing can
crash the harness. `_ingest` runs stages in order:

1. **Firewall** (Stage 0, ~L512) — scan the *raw* body for embedded directives; if
   found, return `no_op` and nothing else. Runs first, in trusted code, *before*
   perception.
2. **Perception → `EvidenceFrame`** (`extract`, ~L433; the frame type ~L413) — the
   **single place** raw body is read. It emits a typed bundle of classification
   signals (entities, direction, phenomenon cues) and nothing that carries magnitude
   or a command. Everything below consumes the frame, never the text.
3. **Strength** — a scalar `S ∈ [0,1]` computed from provenance only.
4. **OOD** (`decide_ood`, ~L291) — is this outside the model? Decided structurally
   (potency/lineage over the graph), precision-first, defaulting to in-model.
5. **In-model decision** (Stage 4, ~L542) — contradiction vs confirmation; the
   skepticism gate (hold thin extraordinary claims pending); direction handling.
6. **Magnitude** (Stage 5, ~L458) — turn `S` into a bounded log-odds move and emit
   the `Delta` list.

### The firewall boundary, precisely

The firewall scan (step 1) runs on raw body in **trusted** code and is deliberately
**outside** the perception seam — so if we ever swap `extract` for an LLM, a flagged
item is never even handed to the (untrusted) model. `tests/seam_guard.py` enforces,
structurally, that raw text is read *only* inside `extract` and the firewall scanner —
if anyone adds a keyword check in the decision layer, the build fails.

---

## 5. How we got here (why the code looks like this)

The shape of the code is the residue of a specific journey. Knowing it will save you
from re-fighting battles we already lost.

1. **Base submission.** Rule-based `ingest`, all practice + hard checks green.
2. **Adversarial hardening.** We wrote probes for unfamiliar wording, injection
   evasion, provenance spoofs, and pending-resolution sequences, and fixed what they
   exposed. This worked, but revealed a ceiling: **keyword lists are a losing arms
   race** against wording the hidden set will use that we can't enumerate.
3. **Structural classification.** The fix for the ceiling was to decide from the
   **graph** (potency levels, lineage, the domain declaration) rather than from
   prose — using text only to extract *which states* and *what direction*. This
   closed whole classes of misses at once.
4. **Two regressions, both instructive** (details in `IMPROVEMENTS.md`):
   - Direction detection first leaned on the substring `"differentiat"`, then on
     **word order** — which shipped a *worse* bug (a strong reprogramming result
     phrased destination-first was read as forward and silently dropped, a false
     negative on the 40-pt axis). It passed a 12/12 test suite because the same
     person wrote the fix and the tests and shared a blind spot.
   - The follow-up (adding production verbs like "produced") re-opened a false
     negative on *participle* phrasing — the same verb as a passive participle.
   Both were caught only by probes that attacked **both** directions of the rule.
5. **The perception seam.** We collapsed the ~8 scattered body-reads into the single
   `extract → EvidenceFrame` function and added `seam_guard.py` to keep it that way.
   This makes the extraction layer one testable surface — and makes an LLM extractor
   a genuine drop-in *if* we ever want one (§8).

The throughline: **prefer a structural fix to a longer keyword list; and never trust
a green suite you wrote alongside your own fix.**

---

## 6. Running everything

Python 3.10+, standard library only. From the repo root:

```bash
python selfcheck.py                       # the official practice sandbox
python tests/hard_selfcheck.py            # 12-item stream on the real seed → /100
python tests/<name>.py                    # any dev probe (see table)
```

**Windows note:** some suites print a `Δ`; if the console errors on it, prefix with
`PYTHONIOENCODING=utf-8` (the harnesses also self-reconfigure stdout where they can).

The dev probe suites (`tests/`) are our **regression net** — not a source of new
points, but the thing that lets us change the solution without silently breaking it:

| Suite | What it guards |
|-------|----------------|
| `hard_selfcheck.py` | the four scored axes, approximated, on the real seed (→ /100) |
| `adversarial_probe.py` | unfamiliar wording, injection evasion, provenance spoof, pending sequences |
| `trajectory_probe.py` | cumulative confidence *shape* (no drift / bounded / no rebound) |
| `ood_subtype_probe.py` | `propose_axis` vs `propose_regime` + the right name |
| `malformed_provenance_probe.py` | missing/garbage/non-dict inputs degrade to no-op, never crash |
| `paraphrase_probe.py` | re-worded items preserve their verdict (measures lexical coupling) |
| `renamed_seed_probe.py` | rename every entity to arbitrary tokens → identical verdicts (no name-coupling) |
| `direction_probe.py` | attacks **both** direction errors; `N8` is a known hole tracked as an `XFAIL` |
| `extract_probe.py` | pins `extract()`'s output — the perception seam / an LLM's target schema |
| `seam_guard.py` | AST check: raw text is read only in `extract` + firewall, nowhere else |

Green-check one-liner (the `PYTHONIOENCODING` keeps the `Δ`-printing suites happy on
Windows):

```bash
for f in selfcheck.py tests/*.py; do PYTHONIOENCODING=utf-8 python "$f" >/dev/null 2>&1 && echo "OK   $f" || echo "FAIL $f"; done
```

---

## 7. Key decisions and why

Each maps to a specific failure it prevents:

- **Provenance = magnitude, body = classification only.** Prevents *trust-the-body*
  (a spoofed "replicated by 250 labs" in the text) and makes the firewall structural.
- **Structural OOD, not lexical.** A potency-*changing* move is in-model even if it
  sounds exotic (beats the near-miss precision trap); a potency-*preserving* jump
  between identities is out-of-model. Prevents *flag-everything*.
- **Direction: forward requires positive evidence; ambiguity defaults backward.**
  Grounded in claim C1 (transitions don't increase potency, and `potency_level` is
  inverted, so a lower-potency destination is the law-violating, newsworthy reading).
  The two directions are asymmetric — a missed reprogramming is a 40-pt false
  negative, while forward differentiation is already near-certain and never news.
- **Skepticism keys off provenance thinness, never recognition.** A single-source
  unreplicated claim is *held pending*, then resolved on later evidence. The hidden
  set contains a *fabricated* false alarm with no real-world counterpart, so
  "recognizing the answer" earns nothing — only genuine provenance-based skepticism.
- **Rules, not an LLM — conditionally.** For this closed, fully-modeled domain, rules
  are near-optimal and an LLM adds nondeterminism risk for little gain. See §8.

## 8. Open questions & where you can help

- **The endpoint question (dispositive).** `RULES.md` says *if* the organizers
  provide a shared model endpoint, we may call it from `ingest`. We have not
  confirmed whether one exists. That single fact decides whether the neural
  extraction layer is worth building. **If you can find out, that's high-value.** If
  yes: an LLM extractor is now a drop-in behind the rules fallback (the seam in §4
  exists precisely for this) — it emits the same `EvidenceFrame`, touches nothing
  downstream, and removes the keyword brittleness entirely. If no: no network is
  assumed at evaluation, and the rules path is correct by necessity.
- **The tracked direction hole (`direction_probe.py` N8).** A genuinely-forward
  result that puts the source in an oblique non-`from` phrase ("arose in cultures
  *seeded with* PSC") defaults backward and is revised spuriously. It's the
  less-harmful error and is kept *visible* as an `XFAIL` rather than hidden. Fair game
  to narrow further — but read the two cautionary tales in `IMPROVEMENTS.md` first.
- **Better generalization probes.** The paraphrase and renamed-seed harnesses measure
  brittleness structurally rather than by guessing vocabulary. More in that spirit
  (new potency/lineage configs, unseen provenance encodings) is worth more than new
  synonyms.

### Two rules of the road (learned the hard way)

1. **Prefer a structural fix over a longer keyword list.** The latter has a low
   ceiling and is fragile against text we can't see.
2. **A green suite you wrote alongside your own fix is not evidence.** Probes must
   attack *both* directions of a rule, and along *every dimension its assumption
   varies* (we missed grammatical role once and it cost us a regression). Record
   known holes as visible `XFAIL`s — an unrecorded hole is how the first one survived.
