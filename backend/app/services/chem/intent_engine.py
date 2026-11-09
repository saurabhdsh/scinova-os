"""Scientific intent understanding.

A question is scored from its speech act and its scientific object.
Deterministic locks stop a definition from becoming a database lookup.
An optional language-model suggestion is accepted only when it does not
cross those locks.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_EXPLAIN = re.compile(
    r"\b(what(?:'s| is| does| do| are)?|explain|mean(?:s|ing)?|define|definition|corresponds?|tell me about)\b",
    re.I,
)
_PCHEMBL = re.compile(
    r"p\s*-?\s*chembl(?:\s+value)?(?:\s+(?:of|is|=|:))?\s*(\d+(?:\.\d+)?)?",
    re.I,
)
_LIPINSKI = re.compile(r"lipinski|rule of five", re.I)
_TANIMOTO = re.compile(r"\btanimoto\b", re.I)
_AGONIST_WORD = re.compile(r"\bagonists?\b", re.I)
_ANTAGONIST_WORD = re.compile(r"\bantagonists?\b", re.I)
_INHIBITOR_WORD = re.compile(r"\binhibitors?\b", re.I)
_RETRIEVE = re.compile(
    r"\b(retrieve|fetch|find|show|list|get|pull)\b",
    re.I,
)
_BIOACTIVE_OBJECT = re.compile(
    r"\b(agonists?|antagonists?|inhibitors?|ligands?|actives?|bioactives?|compounds?)\b",
    re.I,
)
_NOVELTY = re.compile(
    r"\b(novel|novelty)\b|\bhow similar\b|\bsimilarity (?:to|versus|against|with)\b",
    re.I,
)
_GENERATE = re.compile(
    r"\b(generate|generation|de novo)\b|\bdesign\s+\d+|\bpropose\b.+\bmolecules?\b|"
    r"\bdesign\s+(?:a\s+)?(?:small\s+)?(?:set|molecules|candidates)\b|"
    r"\b(\d+)\s+(?:structurally\s+diverse\s+)?candidates?\b",
    re.I,
)
_OPTIMIZE = re.compile(
    r"\b(optimi[sz]e|improve|increase|decrease|modify|analogue|analog)\b",
    re.I,
)
_PROPERTY = re.compile(
    r"\b(solubility|soluble|logp|clogp|permeability|clearance|stability|potency|selectivity|mw|molecular weight)\b",
    re.I,
)
_DOCK = re.compile(r"\bdock(?:ing)?\b|\bbinding pose\b", re.I)
_DESIGN_TABLE = re.compile(
    r"\btable\b.+\b(?:designed|candidates?|molecules?)\b|"
    r"\b(?:each|every|all)\b.+\bdesigned\b.+\b(?:smiles|propert|bioactiv|admet)\b|"
    r"\bdesigned molecules?\b.+\b(?:table|smiles|bioactiv)\b",
    re.I,
)
_ADMET = re.compile(
    r"\badmet\b|\bherg\b|\bpermeability\b|\bclearance\b|"
    r"\b(?:how many|what|which)\b.+\bpropert(?:y|ies)\b|"
    r"\bpropert(?:y|ies)\b.+\b(?:predict(?:ed)?|calculated|descriptor)\b|"
    r"\bpredict(?:ed)?\b.+\bpropert(?:y|ies)\b|"
    r"\bphysicochemical\b|\bdescriptors?\b",
    re.I,
)
_SYNTH = re.compile(r"\bretrosynth|\bsynthe(?:sis|size|tic)\b|\broute\b", re.I)
_RANK = re.compile(
    r"\btop\s+\d+\b|\bwhich (?:\w+\s+){0,3}(?:first|better)\b|\bhighest\b.+\bqed\b|\binvestigate first\b",
    re.I,
)
_POCKET = re.compile(r"druggab|binding.?pocket|binding.?site|\bpockets?\b", re.I)
_ROLE = re.compile(r"biological role|\bpathway\b|signal transduction|signaling cascade", re.I)
_STRUCTURES = re.compile(
    r"crystal structure|available structure|structures?\s+(?:of|for|exist|in the)|"
    r"how many structure|what structure|protein data bank|\bpdb\b",
    re.I,
)
_STRATEGY = re.compile(
    r"help me understand|binding strateg|understand the target|identify potential|"
    r"potential binding|before (?:any |we )?(?:design|generat)|atp[-\s]?competitive",
    re.I,
)
_APPROVE = re.compile(
    r"\b(approve|approved|go ahead|proceed|yes,? run|run the campaign|run it)\b",
    re.I,
)
_COUNT = re.compile(r"\b(\d+)\b")
_INDEX = re.compile(r"\b(?:molecule|candidate|analogue|analog)\s+(\d+)\b", re.I)
_GREETING = re.compile(
    r"^(?:(?:well|oh|um|so|ok|okay)[, ]+)?(?:hi|hello|hey|hiya|howdy|yo|"
    r"good\s+(?:morning|afternoon|evening)|thanks|thank you|thx|bye|goodbye|see you|cheers)"
    r"(?:\s+there)?[!.,?\s]*$",
    re.I,
)
_SOCIAL = re.compile(
    r"\b(how are you|how're you|how's it going|who are you|what are you|what can you do|"
    r"what do you do|your name|tell me a joke|nice to meet|what's up|whats up)\b",
    re.I,
)
_CHEMISTRY = re.compile(
    r"\b(protein|receptor|kinase|enzyme|ligand|molecule|compound|drug|structure|pdb|pocket|"
    r"agonist|antagonist|inhibitor|dock|admet|qed|smiles|chembl|potency|soluble|scaffold|"
    r"peptide|gpcr|binding|assay|target|candidate|novel|design|generat)\b",
    re.I,
)
_WORK = re.compile(
    r"\b(this protein|this target|this session|these (?:molecules|candidates|ligands|structures)|"
    r"the (?:candidates?|ligands?|structures?|molecules?|pocket)|"
    r"we (?:have|stored|designed|retrieved)|so far|where are we|what(?:'s| is) next|next step)\b",
    re.I,
)


def _blank(**overrides: Any) -> dict[str, Any]:
    record = {
        "primaryIntent": "CONVERSATIONAL_FOLLOWUP",
        "capability": "CX",
        "scientificConcept": None,
        "numericValue": None,
        "modality": None,
        "count": None,
        "moleculeIndex": None,
        "requiresExternalTool": False,
        "requiresMoleculeGeneration": False,
        "requiresCompoundRetrieval": False,
        "requiresSimilarity": False,
        "confidence": 0.45,
        "locked": False,
        "method": "deterministic",
        "specialist": "Conversation",
    }
    record.update(overrides)
    return record


def _modality(query: str) -> str | None:
    if _AGONIST_WORD.search(query) and not _ANTAGONIST_WORD.search(query):
        return "agonist"
    if _ANTAGONIST_WORD.search(query):
        return "antagonist"
    if _INHIBITOR_WORD.search(query) and not _AGONIST_WORD.search(query):
        return "inhibitor"
    return None


def _definition(query: str) -> dict[str, Any] | None:
    """A conceptual question. The word ChEMBL inside pChEMBL is not a lookup."""
    text = query or ""
    asks = bool(_EXPLAIN.search(text))
    pchembl = _PCHEMBL.search(text)
    if pchembl and (asks or re.search(r"\bp\s*-?\s*chembl\b", text, re.I)):
        # "Retrieve compounds with pChEMBL above 7" is a lookup, not a definition.
        if _RETRIEVE.search(text) and _BIOACTIVE_OBJECT.search(text):
            return None
        raw = pchembl.group(1)
        value = float(raw) if raw else None
        return _blank(
            primaryIntent="SCIENTIFIC_EXPLANATION",
            capability="EXPLAIN",
            scientificConcept="pChEMBL",
            numericValue=value,
            confidence=0.97,
            locked=True,
            specialist="Scientific explanation",
        )
    if not asks:
        return None
    if _LIPINSKI.search(text):
        return _blank(
            primaryIntent="SCIENTIFIC_EXPLANATION",
            capability="EXPLAIN",
            scientificConcept="Lipinski rule of five",
            confidence=0.96,
            locked=True,
            specialist="Scientific explanation",
        )
    if _TANIMOTO.search(text) and not _NOVELTY.search(text):
        return _blank(
            primaryIntent="SCIENTIFIC_EXPLANATION",
            capability="EXPLAIN",
            scientificConcept="Tanimoto similarity",
            confidence=0.94,
            locked=True,
            specialist="Scientific explanation",
        )
    if re.search(r"\bwhat (?:is|does) an? (agonist|antagonist)\b", text, re.I):
        concept = "agonist" if _AGONIST_WORD.search(text) else "antagonist"
        return _blank(
            primaryIntent="SCIENTIFIC_EXPLANATION",
            capability="EXPLAIN",
            scientificConcept=concept,
            confidence=0.93,
            locked=True,
            specialist="Scientific explanation",
        )
    return None


def _pending_generation(session: dict[str, Any] | None) -> bool:
    for row in (session or {}).get("workflows") or []:
        if row.get("kind") == "molecule_generation" and row.get("status") in {"READY", "CREATED"}:
            return True
    return False


def is_open_conversation(query: str, session: dict[str, Any] | None = None) -> bool:
    """A greeting or a question that is not about the work stored in this session."""
    text = (query or "").strip()
    if not text:
        return False
    if _GREETING.match(text):
        return True
    if _SOCIAL.search(text) and not (_PCHEMBL.search(text) or _LIPINSKI.search(text)):
        return True
    target = (session or {}).get("target") or {}
    gene = str(target.get("gene_symbol") or "")
    if gene and re.search(rf"\b{re.escape(gene)}\b", text, re.I):
        return False
    if _WORK.search(text) or (_CHEMISTRY.search(text) and gene):
        return False
    in_session = bool(gene or (session or {}).get("structures") or (session or {}).get("cards"))
    if in_session and len(text.split()) <= 14 and re.search(r"\b(again|repeat|that|this|continue|go on)\b", text, re.I):
        return False
    return True


def _chat_turn(text: str, session: dict[str, Any] | None) -> dict[str, Any]:
    return _validate(_blank(
        primaryIntent="CONVERSATIONAL_FOLLOWUP",
        capability="CHAT",
        confidence=0.92,
        locked=True,
        specialist="Conversation",
    ), text)


def classify_scientific_intent(query: str, session: dict[str, Any] | None = None) -> dict[str, Any]:
    text = query or ""
    greeting = _GREETING.match(text.strip()) or (
        _SOCIAL.search(text) and not (_PCHEMBL.search(text) or _LIPINSKI.search(text) or _definition(text))
    )
    if greeting:
        return _chat_turn(text, session)
    defined = _definition(text)
    if defined:
        return _validate(defined, text)

    if _APPROVE.search(text) and _pending_generation(session):
        return _validate(_blank(
            primaryIntent="WORKFLOW_EXECUTION",
            capability="APPROVE",
            confidence=0.9,
            locked=True,
            specialist="Workflow",
        ), text)

    modality = _modality(text)
    count = None
    count_match = re.search(
        r"\b(\d+)\s+(?:small\s+)?(?:molecules?|candidates?|structures?|analog(?:ue)?s?)\b",
        text,
        re.I,
    )
    if count_match:
        count = int(count_match.group(1))
    index_match = _INDEX.search(text)
    molecule_index = int(index_match.group(1)) if index_match else None

    if _NOVELTY.search(text) or (_TANIMOTO.search(text) and not _EXPLAIN.search(text)):
        return _validate(_blank(
            primaryIntent="SIMILARITY_ASSESSMENT",
            capability="C4",
            modality=modality,
            requiresSimilarity=True,
            confidence=0.93,
            locked=True,
            specialist="Molecular Similarity",
        ), text)

    if _OPTIMIZE.search(text) and (_PROPERTY.search(text) or molecule_index or re.search(r"\bthis molecule\b", text, re.I)):
        if not (_GENERATE.search(text) and not molecule_index):
            return _validate(_blank(
                primaryIntent="LEAD_OPTIMIZATION",
                capability="OPT",
                moleculeIndex=molecule_index,
                count=count,
                confidence=0.9,
                locked=True,
                specialist="Lead Optimization",
            ), text)

    if _GENERATE.search(text) and not (_STRATEGY.search(text) and not re.search(r"\b(generate|generation)\b|\bdesign\s+\d+", text, re.I)):
        return _validate(_blank(
            primaryIntent="MOLECULE_GENERATION",
            capability="C3",
            count=count or 12,
            modality=modality,
            requiresMoleculeGeneration=True,
            confidence=0.9,
            specialist="Molecular Generation",
        ), text)

    if _DOCK.search(text):
        return _validate(_blank(
            primaryIntent="DOCKING",
            capability="DOCK",
            requiresExternalTool=True,
            confidence=0.9,
            locked=True,
            specialist="Docking and Binding Analysis",
        ), text)

    if re.search(r"\bbinding interactions?\b", text, re.I):
        return _validate(_blank(
            primaryIntent="STRUCTURAL_ANALYSIS",
            capability="STRUCT",
            confidence=0.86,
            locked=True,
            specialist="Structural Biology",
        ), text)

    if re.search(
        r"\b(can|could|do|are) you\b.+\bpredict(?:ed)?\b.+\b(admet|propert|descriptor)|\bcan you predict(?:ed)? admet\b",
        text,
        re.I,
    ) and not re.search(r"\b(this|that|each|every|designed) molecule\b|\bmolecule\s+\d+\b", text, re.I):
        return _validate(_blank(
            primaryIntent="SCIENTIFIC_EXPLANATION",
            capability="EXPLAIN",
            scientificConcept="ADMET prediction",
            confidence=0.94,
            locked=True,
            specialist="Scientific explanation",
        ), text)

    if _DESIGN_TABLE.search(text):
        return _validate(_blank(
            primaryIntent="ADMET",
            capability="TABLE",
            confidence=0.9,
            locked=True,
            specialist="ADMET Prediction",
        ), text)

    if _ADMET.search(text) and not _OPTIMIZE.search(text):
        return _validate(_blank(
            primaryIntent="ADMET",
            capability="ADMET",
            moleculeIndex=molecule_index,
            confidence=0.86,
            specialist="ADMET Prediction",
        ), text)

    if _SYNTH.search(text) and not re.search(r"\broute of administration\b", text, re.I):
        return _validate(_blank(
            primaryIntent="RETROSYNTHESIS",
            capability="C7",
            moleculeIndex=molecule_index,
            confidence=0.84,
            specialist="Retrosynthesis",
        ), text)

    if _RANK.search(text):
        return _validate(_blank(
            primaryIntent="SCIENTIFIC_COMPARISON",
            capability="RANK",
            count=count,
            confidence=0.84,
            specialist="Medicinal Chemistry Reasoning",
        ), text)

    from app.services.chem.target_intel import asks_for_known_drugs

    retrieval = (
        asks_for_known_drugs(text)
        or (_RETRIEVE.search(text) and _BIOACTIVE_OBJECT.search(text))
        or re.search(r"\bfrom chembl\b", text, re.I)
        or re.search(r"\bknown\b.+\b(agonists?|antagonists?|inhibitors?|ligands?|actives?)\b", text, re.I)
    )
    if retrieval and not defined:
        return _validate(_blank(
            primaryIntent="KNOWN_BIOACTIVE_RETRIEVAL",
            capability="C2",
            modality=modality,
            requiresCompoundRetrieval=True,
            requiresExternalTool=True,
            confidence=0.9,
            specialist="Known Bioactive Discovery",
        ), text)

    if re.search(r"\b[0-9][A-Za-z0-9]{3}\b", text) and re.search(r"\b(dossier|retrieve|structure of|pdb)\b", text, re.I):
        return _validate(_blank(
            primaryIntent="STRUCTURE_RETRIEVAL",
            capability="C6D",
            requiresExternalTool=True,
            confidence=0.8,
            specialist="Structural Biology",
        ), text)

    if _POCKET.search(text):
        return _validate(_blank(
            primaryIntent="STRUCTURAL_ANALYSIS",
            capability="C6P",
            requiresExternalTool=True,
            confidence=0.82,
            specialist="Structural Biology",
        ), text)

    if _STRUCTURES.search(text) or re.search(r"\b(uniprot|target profile)\b", text, re.I):
        return _validate(_blank(
            primaryIntent="TARGET_RETRIEVAL",
            capability="C1",
            requiresExternalTool=True,
            confidence=0.86,
            specialist="Target Intelligence",
        ), text)

    if _ROLE.search(text):
        return _validate(_blank(
            primaryIntent="TARGET_RETRIEVAL",
            capability="ROLE",
            requiresExternalTool=True,
            confidence=0.9,
            locked=True,
            specialist="Pathway Insight",
        ), text)

    if re.search(r"\b(compare|better than|versus|which of these)\b", text, re.I):
        return _validate(_blank(
            primaryIntent="SCIENTIFIC_COMPARISON",
            capability="RANK" if re.search(r"\b(which|better|top)\b", text, re.I) else "CX",
            modality=modality,
            confidence=0.7,
            specialist="Medicinal Chemistry Reasoning",
        ), text)

    if re.search(r"\b3d\b|visuali[sz]|mol\*|molstar|\brender\b", text, re.I):
        return _validate(_blank(
            primaryIntent="STRUCTURAL_ANALYSIS",
            capability="C6",
            confidence=0.8,
            specialist="Molecular Visualization",
        ), text)

    if re.search(r"\b(export|report|save this|save the session)\b", text, re.I):
        return _validate(_blank(
            primaryIntent="WORKFLOW_EXECUTION",
            capability="C8",
            confidence=0.8,
            specialist="Orchestrator",
        ), text)

    if _STRATEGY.search(text):
        return _validate(_blank(
            primaryIntent="CONVERSATIONAL_FOLLOWUP",
            capability="CX",
            modality=modality,
            confidence=0.78,
            specialist="Medicinal Chemistry Reasoning",
        ), text)

    from app.services.chem.target_intel import extract_gene_symbol

    if extract_gene_symbol(text):
        return _validate(_blank(
            primaryIntent="TARGET_RETRIEVAL",
            capability="C1",
            requiresExternalTool=True,
            confidence=0.9,
            locked=True,
            specialist="Target Intelligence",
        ), text)
    if is_open_conversation(text, session):
        return _chat_turn(text, session)
    target = (session or {}).get("target") or {}
    if target.get("gene_symbol") or (session or {}).get("structures"):
        return _maybe_llm(_blank(
            primaryIntent="CONVERSATIONAL_FOLLOWUP",
            capability="CX",
            modality=modality,
            confidence=0.55,
            specialist="Conversation",
        ), text, session)
    return _maybe_llm(_blank(
        primaryIntent="CONVERSATIONAL_FOLLOWUP",
        capability="CONTEXT",
        confidence=0.6,
        specialist="Conversation",
    ), text, session)


def _validate(draft: dict[str, Any], query: str) -> dict[str, Any]:
    """Locks outrank any later suggestion. A definition never retrieves compounds."""
    if draft.get("locked") and draft.get("primaryIntent") == "SCIENTIFIC_EXPLANATION":
        draft["requiresExternalTool"] = False
        draft["requiresMoleculeGeneration"] = False
        draft["requiresCompoundRetrieval"] = False
        draft["requiresSimilarity"] = False
        draft["capability"] = "EXPLAIN"
    if draft.get("primaryIntent") == "SIMILARITY_ASSESSMENT":
        draft["requiresMoleculeGeneration"] = False
        draft["requiresCompoundRetrieval"] = False
        draft["capability"] = "C4"
    if _PCHEMBL.search(query or "") and draft.get("primaryIntent") != "KNOWN_BIOACTIVE_RETRIEVAL":
        if _EXPLAIN.search(query or "") or re.fullmatch(r"\s*what is p\s*-?\s*chembl.*", query or "", re.I):
            draft["primaryIntent"] = "SCIENTIFIC_EXPLANATION"
            draft["capability"] = "EXPLAIN"
            draft["requiresCompoundRetrieval"] = False
            draft["locked"] = True
    return draft


_ALLOWED = {
    "SCIENTIFIC_EXPLANATION": "EXPLAIN",
    "TARGET_RETRIEVAL": "C1",
    "STRUCTURE_RETRIEVAL": "C6D",
    "KNOWN_BIOACTIVE_RETRIEVAL": "C2",
    "MOLECULE_GENERATION": "C3",
    "MOLECULAR_MODIFICATION": "OPT",
    "SIMILARITY_ASSESSMENT": "C4",
    "DOCKING": "DOCK",
    "ADMET": "ADMET",
    "LEAD_OPTIMIZATION": "OPT",
    "RETROSYNTHESIS": "C7",
    "EXPERIMENTAL_INTERPRETATION": "CX",
    "SCIENTIFIC_COMPARISON": "RANK",
    "STRUCTURAL_ANALYSIS": "STRUCT",
    "WORKFLOW_EXECUTION": "APPROVE",
    "CONVERSATIONAL_FOLLOWUP": "CX",
}


def _maybe_llm(draft: dict[str, Any], query: str, session: dict[str, Any] | None) -> dict[str, Any]:
    if draft.get("locked") or draft.get("confidence", 0) >= 0.8:
        return draft
    try:
        from app.config import settings
        from app.services.llm_service import llm_service
    except Exception:
        return draft
    if not getattr(settings, "chem_intent_llm", False) or not llm_service.available:
        return draft
    target = (session or {}).get("target") or {}
    prompt = json.dumps({
        "message": query,
        "target": target.get("gene_symbol"),
        "designed_molecules": len((session or {}).get("candidates") or []),
        "known_ligands": len((session or {}).get("actives") or []),
        "allowed_intents": sorted(_ALLOWED),
    })
    system = (
        "Classify one scientist message. Return JSON with primaryIntent, "
        "requiresCompoundRetrieval, requiresMoleculeGeneration, requiresExternalTool. "
        "A definition such as pChEMBL must be SCIENTIFIC_EXPLANATION and must not retrieve compounds. "
        "Do not invent data."
    )
    try:
        raw = llm_service.chat_json(system, prompt, temperature=0.0)
    except Exception as exc:
        logger.info("Intent model unavailable: %s", exc)
        return draft
    if not isinstance(raw, dict):
        return draft
    primary = str(raw.get("primaryIntent") or "")
    if primary not in _ALLOWED:
        return draft
    suggested = dict(draft)
    suggested["primaryIntent"] = primary
    suggested["capability"] = _ALLOWED[primary]
    suggested["method"] = "llm+deterministic"
    suggested["confidence"] = 0.7
    if raw.get("requiresCompoundRetrieval") is True and primary != "SCIENTIFIC_EXPLANATION":
        suggested["requiresCompoundRetrieval"] = True
    return _validate(suggested, query)
