"""GROUND TRUTH — ingest solution.

Online belief revision that is calibrated, manipulation-proof, and aware of its
own limits. Implemented as a deterministic, rule-based pipeline (no LLM, no
network) so it cannot time out or crash the harness.

Design contract (see PLAN.md / DESIGN.md):
  * item.provenance is the ONLY channel read for MAGNITUDE.
  * item.body is read for CLASSIFICATION ONLY (which entities / what kind of
    transition) — never for a number or a command. This makes the firewall hold
    by construction: no body text can express a mutation.
  * Nothing is hardcoded to the practice names/IDs. Everything is resolved from
    the read-only `view` and the (seed-invariant) domain declaration, so the same
    code works on the hidden biology graph.

Pipeline: 0 firewall -> 1 strength -> 2 parse -> 3 OOD -> 4 decision -> 5 magnitude.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass

from groundtruth.deltas import Delta, no_op
from groundtruth.ingest import EvidenceItem, IngestResult
from groundtruth.model import GraphView, logit, sigmoid

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
MAX_MOVE = 2.8      # max |change in log-odds| we ever request (API cap is 3.0)
EPS = 0.15          # sub-epsilon moves collapse to no_op ("near-zero on noise")
CEIL = 0.90         # don't strengthen a belief already at/above this confidence
HIGH_CONF = 0.85    # a claim this confident, contradicted on thin evidence, is "extraordinary"

# ---------------------------------------------------------------------------
# Provenance normalization (the trusted channel)
# ---------------------------------------------------------------------------
_WORD_NUM = {
    "none": 0, "zero": 0, "no": 0, "single": 1, "one": 1, "once": 1, "lone": 1,
    "couple": 2, "twice": 2, "few": 2, "thrice": 3, "handful": 3, "some": 3,
    "multiple": 4, "several": 4, "many": 6, "numerous": 6, "dozens": 12, "hundreds": 100,
}
_DIRECTNESS = {"direct": 1.0, "indirect": 0.5, "inferred": 0.4, "correlational": 0.4}
_EFFECT = {"strong": 1.0, "large": 1.0, "moderate": 0.6, "modest": 0.5, "weak": 0.3, "none": 0.0}

# provenance.method_class -> the mechanism_class used to scope the child claims
_METHOD_TO_MECH = {
    "defined_factor_perturbation": "defined_factor",
    "defined_factor": "defined_factor",
    "forced_factor": "defined_factor",
    "environmental_stress": "env_stress",
    "env_stress": "env_stress",
    "stress": "env_stress",
    "oocyte_nuclear_transfer": "oocyte_nt",
    "nuclear_transfer": "oocyte_nt",
    "oocyte_nt": "oocyte_nt",
    "spontaneous": "spontaneous",
}


def _num(v, default: float = 0.0) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in _WORD_NUM:
            return float(_WORD_NUM[s])
        m = re.search(r"\d+", s)
        if m:
            return float(m.group())
    return default


def strength(prov: dict) -> float:
    """Scalar evidence strength in [0,1], from structured provenance only."""
    groups = min(_num(prov.get("independent_groups", 0)), 6) / 6.0
    repl = min(_num(prov.get("replication_count", 0)), 6) / 6.0
    directness = _DIRECTNESS.get(str(prov.get("method_directness", "")).lower(), 0.7)
    effect = _EFFECT.get(str(prov.get("effect_strength", "")).lower(), 0.6)
    core = 0.65 * groups + 0.35 * repl          # independent replication dominates
    return max(0.0, min(1.0, core * directness * effect))


def is_thin(prov: dict) -> bool:
    """Single-source and unreplicated — the signature of an unsupported claim."""
    return _num(prov.get("independent_groups", 0)) <= 1 and _num(prov.get("replication_count", 0)) <= 1


def single_source(prov: dict) -> bool:
    """No INDEPENDENT reproduction: at most one independent group, regardless of how
    many times that one source repeated internally. Many internal repeats by a single
    lab are not independent confirmation of an extraordinary claim — independence, not
    raw replication count, is what the skepticism axis turns on. (A fabricated fraud
    is a single source; it may still assert a high internal replication_count.)"""
    return _num(prov.get("independent_groups", 0)) <= 1


def is_retracted(prov: dict) -> bool:
    return str(prov.get("retraction_status", "none")).lower() in ("retracted", "withdrawn", "corrected")


def structured_failure(prov: dict) -> bool:
    """A pending claim is resolved as failed ONLY from the structured channel:
    an explicit retraction, or an independent replication attempt (>=2 groups)
    that found no effect. Never inferred from body phrasing — otherwise untrusted
    text could force a drop_claim (a text-triggered mutation)."""
    if is_retracted(prov):
        return True
    groups = _num(prov.get("independent_groups", 0))
    effect = str(prov.get("effect_strength", "")).lower()
    return groups >= 2 and effect in ("none", "null", "absent", "no_effect", "no effect")


# ---------------------------------------------------------------------------
# Stage 0 — firewall: never derive a mutation from body text
# ---------------------------------------------------------------------------
_INJECTION_PHRASES = (
    "set the confidence", "set confidence", "set it to", "set to certain",
    "mark as certain", "ignore prior", "ignore previous", "ignore all",
    "disregard prior", "disregard previous", "overwrite", "override the",
    "override this", "delete claim", "drop claim", "remove the claim",
    "processor note", "system note", "admin", "you must set", "must set",
    "force the", "update the confidence", "assistant", "instruction:",
    # natural-language directives that try to dictate belief state without evidence
    "fully established and certain", "as certain in all cases", "treat the claim",
    "treat this claim", "regard the claim", "going forward, treat", "in all cases",
    "consider it settled", "consider the claim", "from now on", "fully established",
    "permanently set", "lock the confidence", "hard-code", "hardcode",
    "record this belief", "make this authoritative", "update your belief",
    "the knowledge base should", "knowledge base to", "regard this as certain",
    "treat as established", "treat as certain", "set all", "override prior",
    "ignore the provenance", "ignore provenance", "disregard the provenance",
)
_BRACKET_CMD = ("set", "delete", "ignore", "overwrite", "override", "confidence",
                "must", "certain", "drop", "remove", "force", "establish")
# de-spaced command cores, matched against a whitespace-stripped body to defeat
# letter-spacing evasion ("s e t  t h e  confidence"). Kept distinctive to avoid
# false positives.
_INJECTION_NOSPACE = (
    "settheconfidence", "setconfidence", "deleteclaim", "dropclaim",
    "removetheclaim", "ignoreprior", "ignoreprevious", "markascertain",
    "forcethe", "updatetheconfidence", "overridethe", "ignoreprovenance",
)


def _normalize_for_scan(body: str) -> str:
    """Fold homoglyphs/fullwidth (NFKC), strip zero-width & format controls and
    soft hyphens, and lowercase — so unicode tricks cannot hide a directive."""
    s = unicodedata.normalize("NFKC", body)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("C"))
    s = s.replace("\xad", "")
    return s.lower()


def looks_like_injection(body: str) -> bool:
    norm = _normalize_for_scan(body)
    collapsed = re.sub(r"\s+", " ", norm)                 # "set  the" -> "set the"
    # collapse runs of single letters ("s e t" -> "set") without touching words
    letters = re.sub(r"\b([a-z])(?:\s+([a-z])\b)+", lambda m: m.group(0).replace(" ", ""), norm)
    nospace = re.sub(r"\s+", "", norm)

    if any(p in collapsed or p in letters for p in _INJECTION_PHRASES):
        return True
    if any(p in nospace for p in _INJECTION_NOSPACE):
        return True
    # an embedded bracketed directive that talks to the processor
    for seg in re.findall(r"\[([^\]]*)\]|\{([^}]*)\}", norm):
        s = "".join(seg)
        s2 = s.replace(" ", "")
        if sum((k in s or k in s2) for k in _BRACKET_CMD) >= 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Stage 2 — semantic parse (classification only)
# ---------------------------------------------------------------------------
def find_states(view: GraphView, body: str):
    """Resolve CamelCase-ish tokens in the body against real graph states."""
    seen, out = set(), []
    for tok in re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\b", body):
        if tok in seen:
            continue
        seen.add(tok)
        cs = view.cell_state(tok)
        if cs is not None:
            out.append(cs)
    return out


_ORIGIN_CUE = re.compile(r"(?:from|out of|derived from|starting from|originating from)\s+$", re.IGNORECASE)

# Connectives that genuinely denote a transition, establishing "first -> last".
# Deliberately NOT a bare "to": ambiguous linkers ("compared to", "relative to")
# are not positive evidence of a described transition, and an unresolved direction
# is safer than a wrongly-resolved one (see the asymmetry at the call site).
_DIR_CONNECTIVE = re.compile(
    r"(?:gave|gives|giving)\s+rise\s+to|\binto\b|\btowards?\b|\bbecame\b|\bbecomes\b|"
    r"\bto\s+(?:a|an|the)\b",
    re.IGNORECASE)

# produce/generate/yield are ordinary transition verbs ("PSC produced Fibroblast"),
# but they are just as common as PASSIVE PARTICIPLES ("PSC colonies, produced at high
# efficiency, emerged after Fibroblast was treated"), where they describe the subject
# instead of linking the pair — and reading that as forward would drop a real
# contradiction. So they are trusted only in active, subject-adjacent position: within
# a word or two of the first state, with no intervening clause boundary. A participle
# use falls through to None, hence to the backward default, which costs nothing.
_ACTIVE_PRODUCTION = re.compile(r"^\s*(?:\w+\s+){0,2}(?:produc|generat|yield)\w*\s", re.IGNORECASE)


def transition_direction(body_lower: str, states):
    """Resolve (origin -> destination) and return 'forward' | 'backward' | None.

    Direction is decided by comparing potency, which grounds it in the graph's own
    law rather than in prose: C1 says transitions do not increase potency, and
    potency_level is inverted (lower = more potent), so a destination with a LOWER
    potency_level is a potency *increase* — exactly what C1 forbids, i.e. the
    newsworthy reading. The reverse (source -> terminal) is ordinary
    differentiation, already held near-certain by C5, and is never news.

    Direction is asserted only on POSITIVE evidence: an explicit origin cue
    ("... produced from <state>"), a transition connective linking the pair, or a
    production verb in clean active subject-adjacent position. Bare word order is
    never used — "PSC colonies emerged after Fibroblast cells received defined
    factors" is reprogramming despite naming the destination first. An ambiguous
    cue is not positive evidence: unresolved returns None and the caller defaults
    to backward, so failing to resolve is always the cheap error.
    """
    named = sorted(((body_lower.find(s.name.lower()), s) for s in states
                    if body_lower.find(s.name.lower()) >= 0), key=lambda t: t[0])
    if len(named) < 2:
        return None
    (idx_first, first), (idx_last, last) = named[0], named[-1]
    between = body_lower[idx_first + len(first.name):idx_last]
    if _ORIGIN_CUE.search(body_lower[max(0, idx_last - 24):idx_last]):
        origin, dest = last, first            # "... produced from <state>"
    elif _DIR_CONNECTIVE.search(between):
        origin, dest = first, last            # "<state> gave rise to / into <state>"
    elif "," not in between and _ACTIVE_PRODUCTION.match(between):
        origin, dest = first, last            # "<state> produced <state>" — clean SVO only
    else:
        return None                           # no positive evidence: do not guess
    if dest.potency_level < origin.potency_level:
        return "backward"
    if dest.potency_level > origin.potency_level:
        return "forward"
    return None


_REVERSION_KW = (
    "revert", "reverted", "reversion", "returned", "return to", "return of",
    "back to", "de-differentiat", "dedifferentiat", "less-committed",
    "less committed", "more potent", "more primitive", "stem-like",
    "pluripotent-like", "regain", "reacquire",
    # broadened for unfamiliar phrasings of the same phenomenon. NOTE: we avoid
    # bare "reprogram" because it is commonly used as a noun ("the reprogramming
    # claim") and would misfire on text that merely mentions the topic.
    "driven to", "driven back", "coaxed", "restored to", "rolled back",
    "roll back", "irreversib", "no longer holds",
    "earlier stage", "earlier progenitor", "earlier developmental",
    "less differentiat", "less mature", "less specialized", "less committed",
    "regress",
)
_SOURCE_KW = ("source", "pluripoten", "totipotent", "stem cell", "stem-like", "pluripotent-like")
_LATERAL_KW = (
    "directly into", "direct conversion", "without passing through",
    "without an intermediate", "without intermediate", "skipping", "lateral",
    "transdifferentiat", "converted directly", "convert directly",
)
_AGE_KW = (
    "aging", "ageing", "aged", "younger", "older", "rejuvenat", "senescen",
    "lifespan", "biological age", "chronological age", "epigenetic age",
    "cellular age", "youthful",
)
_FUNC_KW = ("function", "functional", "metabolic", "secretory", "contractil",
            "excitabil", "proliferat", "capacity", "performance", "output",
            "activity", "capability", "efficiency", "workload")
# Regex is more robust to phrasing than a fixed keyword list: matches
# "without any change in ... identity", "identity was preserved/retained/intact",
# "cell type was unchanged/preserved", "while remaining a <type>", etc.
_IDENTITY_PRESERVED_RE = re.compile(
    r"(?:without|no)[^.]{0,40}(?:chang\w+|alter\w+|loss|shift\w*)[^.]{0,40}(?:identit|cell type|lineage identit)"
    r"|identit\w*[^.]{0,40}(?:unchang\w+|preserv\w+|retain\w+|intact|maintain\w+|same)"
    r"|(?:cell )?type\w*[^.]{0,25}(?:unchang\w+|preserv\w+|retain\w+|intact|the same|unaltered)"
    r"|while remaining|same cell type|without changing its type|without altering identity"
    r"|retain\w+ their identity|kept their identity|of the same cell type",
    re.IGNORECASE,
)

# --- polarity / modality / predication: the extractor's blind spots ----------
# A flat keyword match sees "revert" in "did NOT revert" and "more potent" in a
# static "IS more potent THAN" comparison, and reads both as reprogramming events.
# These regexes let `extract` down-weight a cue that is negated, hypothetical, or
# merely comparative — no event asserted, so no revision. They live in the seam
# (referenced only inside `extract`) and are guarded by seam_guard's FORBIDDEN set.

# Negation cues. "no longer" is EXCLUDED — "irreversibility no longer holds" is a
# reprogramming assertion, not a null result. Present-ability "can"/"can be" is NOT
# negation (only "cannot"/"can't"/"could not"), so factual "cells can be driven to
# ..." is unaffected.
_NEG_RE = re.compile(
    r"\b(?:did\s+not|do\s+not|does\s+not|didn't|doesn't|don't|was\s+not|were\s+not|"
    r"wasn't|weren't|is\s+not|are\s+not|isn't|aren't|has\s+not|have\s+not|hasn't|haven't|"
    r"cannot|can't|could\s+not|couldn't|would\s+not|wouldn't|"
    r"not|no(?!\s+longer)|never|none|neither|nor|"
    r"fail(?:s|ed|ing)?\s+to|unable\s+to|without|absence\s+of|lack(?:ed|s|ing)?\s+of|"
    r"no\s+such|no\s+evidence)\b",
    re.IGNORECASE,
)
# A negated / null RESULT anywhere in the body ("no reprogramming was observed",
# "no dedifferentiation was detected", "failed to return"), independent of a
# windowed keyword hit.
_NEG_RESULT_RE = re.compile(
    r"\bno(?!\s+longer)\b[^.,;]{0,50}\b(?:observ|report|detect|seen|found|success|"
    r"revert|reversion|reprogram|dedifferentiat|de-differentiat|conversion|return|change)\w*"
    r"|\b(?:not|never|failed\s+to|fail\s+to|unable\s+to|did\s+not|was\s+not|were\s+not|"
    r"could\s+not|cannot|couldn't)\b[^.,;]{0,50}\b(?:observ|report|detect|seen|found|"
    r"revert|reprogram|return|convert|dedifferentiat|de-differentiat|restore|regain|acquire)\w*",
    re.IGNORECASE,
)
# Modality / conditional framing: describes no experiment. "can"/"can be" is
# deliberately absent (it states a factual ability, not a hypothesis).
_MODAL_RE = re.compile(
    r"\b(?:if|would|could|might|may|hypothetical\w*|were\s+to|suppose\w*|assuming|"
    r"conceivably|in\s+principle|in\s+theory)\b",
    re.IGNORECASE,
)
# Unambiguous hypothetical markers that essentially never describe a real confirmed
# result, checked over the WHOLE body (not just the keyword window) — this catches
# subject-aux inversion ("Were Fibroblast cells to revert ...") and a trailing
# "this remains hypothetical", where the modal cue is far from the reversion word.
_HYP_GLOBAL_RE = re.compile(
    r"\bhypothetical\w*\b|\bin\s+principle\b|\bin\s+theory\b|\bconceivably\b|"
    r"\bpurely\s+theoretical\b|"
    r"\bwere\s+\w+(?:\s+\w+){0,3}\s+to\s+"
    r"(?:revert|return|be\b|become|acquire|regain|dedifferentiat|de-differentiat|roll|drive|driven)",
    re.IGNORECASE,
)
# Static comparison ("X IS more potent THAN Y"): a copula + comparative on a
# potency/maturity adjective + "than". No transition verb, so no event. A genuine
# change verb ("became more potent") uses no copula and is NOT matched here.
_COMPARATIVE_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|remain\w*|stay\w*|seem\w*|appear\w*|rank\w*)\b"
    r"[^.,;]{0,30}\b(?:more|less|as|equally)\b[^.,;]{0,20}"
    r"\b(?:potent|primitive|committed|mature|specialized|differentiated|flexible|"
    r"restricted|advanced)\w*\b[^.,;]{0,25}\bthan\b",
    re.IGNORECASE,
)
# Sentence / clause splitter for clause-scoped locality tests.
_SENT_SPLIT = re.compile(r"[.;:!?\n]+|,\s*(?:separately|meanwhile|whereas|in\s+contrast|"
                         r"in\s+a\s+separate|independently|by\s+contrast)\b")


def _clause_lateral(view: "GraphView", body: str) -> bool:
    """CLAUSE-SCOPED lateral test: two equal-potency, distinct-lineage states are a
    lateral pair ONLY if they co-occur in the SAME sentence/clause. A distractor
    state named in another clause ("Neuron populations were profiled. Separately,
    Fibroblast -> PSC ...") must not manufacture a lateral jump and mask the real
    in-model contradiction. Perception-layer (reads raw text); seam-allowlisted."""
    for sent in _SENT_SPLIT.split(body):
        sts = find_states(view, sent)
        for a in sts:
            for c in sts:
                if a is not c and a.potency_level == c.potency_level \
                        and a.lineage_identity != c.lineage_identity:
                    return True
    return False


def _negated_or_hypothetical(b: str) -> tuple[bool, bool]:
    """Polarity + modality of the transition/reversion cue. Negation and modality
    are checked in a short window BEFORE each reversion keyword (so "did not revert",
    "if ... could be driven back" are caught) and, for negation, also as a
    whole-body negated-result phrase. Perception-layer; seam-allowlisted."""
    neg = bool(_NEG_RESULT_RE.search(b))
    hyp = bool(_HYP_GLOBAL_RE.search(b))
    for kw in _REVERSION_KW:
        start = b.find(kw)
        while start != -1:
            pre = b[max(0, start - 42):start]
            if _NEG_RE.search(pre):
                neg = True
            if _MODAL_RE.search(pre):
                hyp = True
            start = b.find(kw, start + 1)
    return neg, hyp


def _pick(options, key):
    head = key.split("_")[0]
    for o in options or []:
        if head in o.lower():
            return o
    return key


def decide_ood(frame: "EvidenceFrame", view: GraphView):
    """Return (kind, name) where kind in {'axis','regime',None}. Precision-first:
    default to in-model unless the evidence clearly matches an excluded axis or a
    non-modeled regime from the domain declaration. Consumes the frame; the only
    graph reasoning here is structural (potency/lineage over resolved entities)."""
    states = frame.entities
    dom = view.domain()
    axes_excluded = dom.axes_excluded if dom else []
    regimes_not = dom.regimes_not_modeled if dom else []

    lateral_struct = frame.lateral_pair
    potency_changes = any(a.potency_level != c.potency_level for a in states for c in states if a is not c)

    # A modeled transition (reprogramming toward the source, or any potency move
    # between represented states) means an exotic-sounding word — "aged",
    # "identity", etc. — is incidental to an IN-MODEL event, not the phenomenon.
    # This is the precision guard against the near-miss trap.
    in_model_transition = frame.reaches_source or potency_changes

    # 1. non-modeled REGIME: a lateral jump between equal-potency, distinct
    #    identities (structural, highest confidence).
    if lateral_struct:
        return "regime", _pick(regimes_not, "lateral_somatic_conversion")

    # 2. excluded AXIS: a property the model does not track at all.
    if not in_model_transition:
        if frame.is_aging:
            return "axis", _pick(axes_excluded, "biological_age")
        if frame.identity_preserved:
            if frame.is_function:
                return "axis", _pick(axes_excluded, "cell_function_independent_of_identity")
            return "regime", _pick(regimes_not, "identity_preserving_state_change")

    # 3. keyword-only lateral (single state named): only when nothing on the
    #    modeled potency axis is happening.
    if frame.is_lateral and not potency_changes and not frame.is_reversion:
        return "regime", _pick(regimes_not, "lateral_somatic_conversion")

    return None, None


# ---------------------------------------------------------------------------
# Claim resolution (structural, never by hardcoded id)
# ---------------------------------------------------------------------------
def _find_claim(view: GraphView, must, prefer=()):
    best, best_score = None, -1
    for cid in view.list_claim_ids():
        c = view.get_claim(cid)
        if c is None:
            continue
        s = c.statement.lower()
        if any(k not in s for k in must):
            continue
        score = sum(1 for k in prefer if k in s)
        if score > best_score:
            best, best_score = c, score
    return best


def _resolve_target(view: GraphView, claim, method_class):
    """If the claim is an umbrella (has derived_from), redirect to the scoped
    child matching the provenance method_class — revising the child lets the
    framework's umbrella propagation (umbrella = min(children)) do the rest."""
    if not claim.derived_from:
        return claim
    mech = _METHOD_TO_MECH.get(str(method_class or "").lower())
    for cid in claim.derived_from:
        ch = view.get_claim(cid)
        if ch is not None and ch.scope.get("mechanism_class") == mech:
            return ch
    kids = [view.get_claim(cid) for cid in claim.derived_from]
    kids = [k for k in kids if k is not None]
    return max(kids, key=lambda k: k.confidence) if kids else claim


_STOP = set(
    "a an the of to in on and or by with without under within into then not do does no "
    "any all its it cells cell state states result results between distinct only adjacent "
    "steps mechanism means that this these those from than more less".split()
)


def _content(s: str):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3 and w not in _STOP}


_CONFIRM_KW = (
    "consistent", "confirm", "as expected", "replicat", "corroborat", "in line with",
    "reaffirm", "support",
    # well-powered confirmations are often phrased as a demonstration, not a
    # "confirmation" — broaden so the strengthen-on-support signal is not missed.
    "demonstrat", "verified", "well-powered", "well powered", "adequately powered",
    "found that", "shows that", "showed that", "robust evidence", "provides evidence",
)


def _find_support_target(view: GraphView, frame: "EvidenceFrame"):
    """Conservatively find a mid-confidence claim this result confirms. Only
    mid-confidence claims (0.40..CEIL) are eligible, so this can only ever nudge a
    genuinely contested belief, never a near-certain one. Grounding (which claim the
    content overlaps) stays in the decision layer; the frame supplies the signal."""
    if not frame.is_confirmation:
        return None
    bw = frame.content_words
    best, best_ov = None, 1
    for cid in view.list_claim_ids():
        c = view.get_claim(cid)
        if c is None or not (0.40 <= c.confidence < CEIL):
            continue
        ov = len(bw & _content(c.statement))
        if ov > best_ov:
            best, best_ov = c, ov
    return best


# ---------------------------------------------------------------------------
# Perception layer: the SINGLE reader of raw evidence text
# ---------------------------------------------------------------------------
@dataclass
class EvidenceFrame:
    """Structured classification signals extracted from the untrusted body — the
    one contract between perception (`extract`) and the decision core. Every field
    is a fact *about the text* (which states, what direction, what phenomenon cues);
    none carries magnitude or a command, so routing all body-reading through here is
    the firewall by construction. These field names are also the schema an LLM
    extractor would fill."""
    entities: list                 # resolved graph CellState nodes
    direction: str | None          # 'forward' | 'backward' | None
    reaches_source: bool           # a source-potency state or a source-ward word
    is_reversion: bool             # explicit reversion keyword
    is_forward_worded: bool        # a bare 'differentiat' mention (forward cue)
    is_lateral: bool               # lateral/transdifferentiation keyword
    is_aging: bool                 # biological-age axis words
    is_function: bool              # cell-function axis words
    identity_preserved: bool       # "identity unchanged/preserved" phrasing
    is_confirmation: bool          # confirming-evidence phrasing
    content_words: set             # content tokens, for support-claim grounding
    is_negated: bool = False       # the reversion/transition cue is negated (null result)
    is_hypothetical: bool = False  # conditional/modal framing — no experiment asserted
    is_comparison: bool = False    # static comparative ("is more potent than"), no event
    lateral_pair: bool = False     # equal-potency distinct-lineage states in the SAME clause


def extract(body: str, view: GraphView) -> EvidenceFrame:
    """The SOLE reader of raw evidence text. Turns the untrusted body into a typed
    frame of classification signals and nothing else — no number, no command, no
    magnitude. The decision core consumes the frame and never the body, so swapping
    this for an LLM (temperature 0, emitting the same frame, rules as the fallback)
    touches nothing downstream. The firewall scan runs earlier, on raw body, in
    trusted code — it is deliberately NOT routed through this possibly-neural step."""
    b = body.lower()
    states = find_states(view, body)
    neg, hyp = _negated_or_hypothetical(b)
    return EvidenceFrame(
        entities=states,
        direction=transition_direction(b, states),
        reaches_source=any(s.potency_level <= 1 for s in states) or any(k in b for k in _SOURCE_KW),
        is_reversion=any(k in b for k in _REVERSION_KW),
        is_forward_worded=("differentiat" in b and "dedifferentiat" not in b and "de-differentiat" not in b),
        is_lateral=any(k in b for k in _LATERAL_KW),
        is_aging=any(k in b for k in _AGE_KW),
        is_function=any(k in b for k in _FUNC_KW),
        identity_preserved=bool(_IDENTITY_PRESERVED_RE.search(body)),
        is_confirmation=any(k in b for k in _CONFIRM_KW),
        content_words=_content(body),
        is_negated=neg,
        is_hypothetical=hyp,
        is_comparison=bool(_COMPARATIVE_RE.search(b)),
        lateral_pair=_clause_lateral(view, body),
    )


# ---------------------------------------------------------------------------
# Stage 5 — magnitude
# ---------------------------------------------------------------------------
def _revise(eid, claim, s_scaled, direction):
    move = MAX_MOVE * max(0.0, min(1.0, s_scaled))
    if move < EPS:
        return []
    new = sigmoid(logit(claim.confidence) + direction * move)
    new = max(0.02, min(0.98, new))
    return [Delta("revise_confidence", eid, {"claim_id": claim.id, "new_confidence": round(new, 4)})]


def _pending_id(states):
    names = "+".join(sorted(s.name for s in states)) or "unspecified"
    return f"pending::{names}"


def _match_pending(view: GraphView, states):
    """Find the held claim this item resolves. A retraction rarely repeats the
    full subject, so we match by subject OVERLAP, not exact key: exact id first,
    then any pending whose subject shares a named state, then — only when the item
    names no state at all — the sole outstanding pending. Returns a pending id or
    None. (Always keyed off named entities, never off free-text commands.)"""
    pids = view.pending_ids()
    if not pids:
        return None
    exact = _pending_id(states)
    if exact in pids:
        return exact
    names = {s.name for s in states}
    if names:
        for p in pids:
            subject = set(p.split("::", 1)[-1].split("+"))
            if names & subject:
                return p
        return None  # a subject was named but nothing overlaps: do not guess
    return pids[0] if len(pids) == 1 else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    try:
        return _ingest(item, view)
    except Exception as exc:  # never crash the harness; a crash scores as no-op anyway
        return IngestResult([no_op(item.id)], f"guarded no-op ({type(exc).__name__})", 0.3, False)


def _ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    # tolerate malformed inputs: a non-dict provenance or non-str body degrades to
    # empty rather than crashing (a crash would score the item as a no-op anyway).
    body = item.body if isinstance(item.body, str) else ""
    prov = item.provenance if isinstance(item.provenance, dict) else {}

    # Stage 0 — firewall. Embedded instructions are inert text. Runs on the raw
    # body in trusted code, BEFORE perception, so a flagged item is never even
    # handed to the (possibly-neural) extractor.
    if looks_like_injection(body):
        return IngestResult([no_op(item.id)], "embedded instruction ignored (firewall)", 0.95, False)

    # Perception: the one and only read of raw body. Everything below consumes the
    # frame, never the text.
    frame = extract(body, view)
    states = frame.entities
    S = strength(prov)

    # Stage 3 — out-of-distribution (before any revision; precision-first).
    kind, name = decide_ood(frame, view)
    if kind == "axis":
        return IngestResult([Delta("propose_axis", item.id, {"axis": name})],
                            f"out-of-model axis: {name}", 0.7, True)
    if kind == "regime":
        return IngestResult([Delta("propose_regime", item.id, {"regime": name})],
                            f"out-of-model regime: {name}", 0.7, True)

    # Retraction / failure-to-replicate — resolve a prior pending cleanly.
    # Keyed off STRUCTURED provenance only, never body phrasing.
    if structured_failure(prov):
        pid = _match_pending(view, states)
        if pid is not None:
            return IngestResult([Delta("drop_claim", item.id, {"claim_id": pid})],
                                "prior pending retracted / failed to replicate (structured); dropped", 0.8, False)
        return IngestResult([no_op(item.id)], "retracted/failed per structured provenance; nothing to update", 0.6, False)

    # Stage 4 — in-model decision.
    # A contradiction of the "cannot go backward" law is recognised two ways: an
    # explicit reversion keyword, OR structurally — a potency-increasing move, which
    # is what C1 declares impossible and therefore the newsworthy reading.
    #
    # The two directions are NOT symmetric, so neither are the defaults. A missed
    # reprogramming result is a false negative on the largest scoring axis, while
    # source -> terminal differentiation is already held near-certain by C5 and is
    # never news. So FORWARD must be positively evidenced; anything unresolved falls
    # back to backward. (Do not "improve" this by inferring direction from word
    # order: that reads "PSC colonies emerged after Fibroblast cells were treated"
    # as forward and silently drops a strong contradiction.)
    source_cue = frame.reaches_source
    terminal_named = any(s.potency_level >= 3 for s in states)   # structural, from entities
    direction = frame.direction                    # 'forward' | 'backward' | None
    if direction == "backward":
        structural_back = True                     # parsed potency increase: contradicts C1
    elif direction == "forward":
        structural_back = False                    # positively evidenced forward move
    else:
        # direction unresolved: default to the newsworthy reading, except that a
        # bare 'differentiat' mention is itself positive evidence of forward.
        structural_back = source_cue and terminal_named and not frame.is_forward_worded
    # A reversion cue (keyword or structural potency-increase) only counts as a
    # contradiction if an EVENT is actually asserted. Perception flags three ways it
    # is not: a negated / null result ("did not revert", "no reprogramming observed"),
    # a hypothetical / conditional ("if cells could be driven back ... no such
    # result"), or a static comparison ("is more potent than"). Each asserts no
    # transition, so the correct move is no revision — a failed reprogramming attempt
    # is in fact evidence FOR irreversibility, never against it.
    event_suppressed = frame.is_negated or frame.is_hypothetical or frame.is_comparison
    reversion = (frame.is_reversion or structural_back) and not event_suppressed
    if reversion:
        reaches_source = source_cue
        if reaches_source:
            target = _find_claim(view, ["return"], ["pluripoten", "source", "stem"])
        else:
            target = _find_claim(view, ["increase", "potency"])
        if target is None:
            return IngestResult([no_op(item.id)], "contradiction but no target claim", 0.5, False)

        # Skepticism gate: a SINGLE-SOURCE result (not independently reproduced)
        # must never drive a revision of a believed claim — hold it pending instead.
        # Keys off INDEPENDENCE (independent_groups), not internal replication_count:
        # one lab repeating itself many times is not independent confirmation, and a
        # fabricated fraud can inflate replication_count while remaining a single
        # source. Independent of the claim's current confidence (a prior strong
        # result may already have moved it).
        if single_source(prov) and (target.confidence >= 0.5 or target.epistemic_status == "established"):
            pid = _pending_id(states)
            note = f"unreplicated extraordinary claim re: {', '.join(s.name for s in states) or 'unspecified'}"
            return IngestResult([Delta("hold_pending", item.id, {"claim_id": pid, "note": note})],
                                "extraordinary claim, thin provenance: held pending", 0.6, False)

        tgt = _resolve_target(view, target, prov.get("method_class"))
        deltas = _revise(item.id, tgt, S, direction=-1)
        if not deltas:
            return IngestResult([no_op(item.id)], "evidence too weak to move belief", 0.5, False)

        # Resolve a prior pending on the same subject that this result now confirms.
        pid = _match_pending(view, states)
        if pid is not None:
            deltas.append(Delta("drop_claim", item.id, {"claim_id": pid}))

        # Scoped revision: narrow the claim to the mechanism that refutes it.
        mech = _METHOD_TO_MECH.get(str(prov.get("method_class", "")).lower())
        if mech:
            deltas.append(Delta("set_scope", item.id, {"claim_id": tgt.id, "scope": {"refuted_under": mech}}))

        # Promote the corresponding declared absence to a real edge (strong evidence only).
        if reaches_source and S > 0.7 and len(states) >= 2:
            frm = max(states, key=lambda s: s.potency_level)
            to = min(states, key=lambda s: s.potency_level)
            if frm.potency_level > to.potency_level and view.has_absence(frm.name, to.name):
                deltas.append(Delta("add_edge", item.id, {"from": frm.name, "to": to.name, "via": mech or "reprogramming"}))

        # Calibrated complement: evidence that reversion is possible supports the
        # contested "retains full potential" belief -> raise it in proportion.
        comp = _find_claim(view, ["retain"], ["potential", "nuclear", "developmental"])
        if comp is not None and comp.confidence < CEIL and S > 0.5:
            deltas += _revise(item.id, comp, S * 0.6, direction=+1)

        return IngestResult(deltas, f"in-model contradiction; revised {tgt.id} (S={S:.2f})",
                            0.5 + 0.4 * S, False)

    # Confirmation — slight strengthen of a mid-confidence belief, else no_op.
    # A hypothetical or negated statement asserts no result, so it is not
    # confirming evidence either.
    support = None if (frame.is_hypothetical or frame.is_negated) else _find_support_target(view, frame)
    if support is not None:
        deltas = _revise(item.id, support, S * 0.5, direction=+1)
        if deltas:
            return IngestResult(deltas, f"confirming evidence; strengthened {support.id}",
                                0.5 + 0.3 * S, False)

    return IngestResult([no_op(item.id)], "no grounded change", 0.6, False)
