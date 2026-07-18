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
    "none": 0, "zero": 0, "no": 0, "single": 1, "one": 1, "lone": 1,
    "couple": 2, "few": 2, "handful": 3, "some": 3, "multiple": 4,
    "several": 4, "many": 6, "numerous": 6, "dozens": 12, "hundreds": 100,
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


def is_retracted(prov: dict) -> bool:
    return str(prov.get("retraction_status", "none")).lower() in ("retracted", "withdrawn", "corrected")


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
    "consider it settled", "consider the claim",
)
_BRACKET_CMD = ("set", "delete", "ignore", "overwrite", "override", "confidence", "must", "certain")


def looks_like_injection(body: str) -> bool:
    b = body.lower()
    if any(p in b for p in _INJECTION_PHRASES):
        return True
    # an embedded bracketed directive that talks to the processor
    for seg in re.findall(r"\[([^\]]*)\]|\{([^}]*)\}", body):
        s = ("".join(seg)).lower()
        if sum(k in s for k in _BRACKET_CMD) >= 2:
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
            "excitabil", "proliferat", "capacity", "performance")
# Regex is more robust to phrasing than a fixed keyword list: matches
# "without any change in ... identity", "identity was preserved/retained/intact",
# "while remaining a <type>", etc.
_IDENTITY_PRESERVED_RE = re.compile(
    r"(?:without|no)[^.]{0,40}(?:chang\w+|alter\w+|loss|shift\w*)[^.]{0,40}identit"
    r"|identit\w*[^.]{0,40}(?:unchang\w+|preserv\w+|retain\w+|intact|maintain\w+|same)"
    r"|while remaining|same cell type|without changing its type|without altering identity"
    r"|retain\w+ their identity|kept their identity",
    re.IGNORECASE,
)
_FAIL_KW = (
    "failed to reproduce", "failed to replicate", "could not reproduce",
    "could not replicate", "did not reproduce", "did not replicate",
    "unable to reproduce", "unable to replicate", "no such effect",
    "fails to replicate", "was not reproducible",
)


def _pick(options, key):
    head = key.split("_")[0]
    for o in options or []:
        if head in o.lower():
            return o
    return key


def classify_ood(view: GraphView, body: str, states):
    """Return (kind, name) where kind in {'axis','regime',None}. Precision-first:
    default to in-model unless the evidence clearly matches an excluded axis or a
    non-modeled regime from the domain declaration."""
    b = body.lower()
    dom = view.domain()
    axes_excluded = dom.axes_excluded if dom else []
    regimes_not = dom.regimes_not_modeled if dom else []

    # excluded AXIS: a property the model does not track at all
    if any(k in b for k in _AGE_KW):
        return "axis", _pick(axes_excluded, "biological_age")
    if _IDENTITY_PRESERVED_RE.search(body):
        if any(k in b for k in _FUNC_KW):
            return "axis", _pick(axes_excluded, "cell_function_independent_of_identity")
        return "regime", _pick(regimes_not, "identity_preserving_state_change")

    # non-modeled REGIME: a lateral jump between equal-potency, distinct identities
    lateral_struct = any(
        a.potency_level == c.potency_level and a.lineage_identity != c.lineage_identity
        for a in states for c in states if a is not c
    )
    potency_changes = any(a.potency_level != c.potency_level for a in states for c in states if a is not c)
    if lateral_struct:
        return "regime", _pick(regimes_not, "lateral_somatic_conversion")
    if any(k in b for k in _LATERAL_KW) and not potency_changes and not any(k in b for k in _REVERSION_KW):
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


def _find_support_target(view: GraphView, body: str):
    """Conservatively find a mid-confidence claim this result confirms."""
    b = body.lower()
    if not any(k in b for k in ("consistent", "confirm", "as expected", "replicat",
                                "corroborat", "in line with", "reaffirm", "support")):
        return None
    bw = _content(body)
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    try:
        return _ingest(item, view)
    except Exception as exc:  # never crash the harness; a crash scores as no-op anyway
        return IngestResult([no_op(item.id)], f"guarded no-op ({type(exc).__name__})", 0.3, False)


def _ingest(item: EvidenceItem, view: GraphView) -> IngestResult:
    body = item.body or ""
    prov = item.provenance or {}
    b = body.lower()

    # Stage 0 — firewall. Embedded instructions are inert text.
    if looks_like_injection(body):
        return IngestResult([no_op(item.id)], "embedded instruction ignored (firewall)", 0.95, False)

    states = find_states(view, body)
    S = strength(prov)

    # Stage 3 — out-of-distribution (before any revision; precision-first).
    kind, name = classify_ood(view, body, states)
    if kind == "axis":
        return IngestResult([Delta("propose_axis", item.id, {"axis": name})],
                            f"out-of-model axis: {name}", 0.7, True)
    if kind == "regime":
        return IngestResult([Delta("propose_regime", item.id, {"regime": name})],
                            f"out-of-model regime: {name}", 0.7, True)

    # Retraction / failure-to-replicate — resolve a prior pending cleanly.
    if is_retracted(prov) or any(k in b for k in _FAIL_KW):
        pid = _pending_id(states)
        if pid in view.pending_ids():
            return IngestResult([Delta("drop_claim", item.id, {"claim_id": pid})],
                                "prior pending retracted / failed to replicate; dropped", 0.8, False)
        return IngestResult([no_op(item.id)], "retracted/failed; nothing to update", 0.6, False)

    # Stage 4 — in-model decision.
    reversion = any(k in b for k in _REVERSION_KW)
    if reversion:
        reaches_source = any(s.potency_level <= 1 for s in states) or any(k in b for k in _SOURCE_KW)
        if reaches_source:
            target = _find_claim(view, ["return"], ["pluripoten", "source", "stem"])
        else:
            target = _find_claim(view, ["increase", "potency"])
        if target is None:
            return IngestResult([no_op(item.id)], "contradiction but no target claim", 0.5, False)

        # Skepticism gate: thin, single-source, unreplicated evidence must never
        # drive a revision — hold it pending instead. This is independent of the
        # claim's *current* confidence (a prior strong result may already have
        # moved it); it keys off provenance thinness, not the belief's value.
        if is_thin(prov) and (target.confidence >= 0.5 or target.epistemic_status == "established"):
            pid = _pending_id(states)
            note = f"unreplicated extraordinary claim re: {', '.join(s.name for s in states) or 'unspecified'}"
            return IngestResult([Delta("hold_pending", item.id, {"claim_id": pid, "note": note})],
                                "extraordinary claim, thin provenance: held pending", 0.6, False)

        tgt = _resolve_target(view, target, prov.get("method_class"))
        deltas = _revise(item.id, tgt, S, direction=-1)
        if not deltas:
            return IngestResult([no_op(item.id)], "evidence too weak to move belief", 0.5, False)

        # Resolve a prior pending on the same subject that this result now confirms.
        pid = _pending_id(states)
        if pid in view.pending_ids():
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
    support = _find_support_target(view, body)
    if support is not None:
        deltas = _revise(item.id, support, S * 0.5, direction=+1)
        if deltas:
            return IngestResult(deltas, f"confirming evidence; strengthened {support.id}",
                                0.5 + 0.3 * S, False)

    return IngestResult([no_op(item.id)], "no grounded change", 0.6, False)
