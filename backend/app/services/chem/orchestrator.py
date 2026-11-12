"""Molecular Discovery Studio orchestrator — intent routing across C1–C8."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.services.chem import session_store
from app.services.chem.chembl_client import discover_known_actives
from app.services.chem.medchem_reasoning import reason_motifs
from app.services.chem.molecule_design import design_candidates
from app.services.chem.novelty import assess_novelty
from app.services.chem.retrosynthesis import assess_synthesis
from app.services.chem.structure_assets import build_visualization_payload, depict_smiles_svg
from app.services.chem.target_intel import biological_role, build_target_profile, extract_gene_symbol
from app.services.chem.structure_dossier import build_structure_dossier, extract_pdb_id
from app.services.chem.conversation_orchestrator import (
    ScientificConversationOrchestrator,
    accept_generated,
    export_session_package,
    generation_failure,
    public_session,
    structure_identity_for_actives,
)
from app.services.chem.pocket_analysis import analyze_pockets
from app.services.chem.research_session import designed_molecules, reference_actives
from app.services.chem.scientific_turn import is_scientific_explanation
from app.services.chem.value_chain_bridge import select_triggered_agents
from app.services.chem.workflow_engine import pending_generation, transition


INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("C1", [r"tell me about", r"target profile", r"what is", r"uniprot", r"structures for", r"about\s+(?!the\b|this\b|these\b|those\b|that\b)[a-z0-9]"]),
    ("C2", [r"known.*(inhibitor|active|ligand)", r"chembl", r"show.*inhibitor", r"bioactive", r"potent.*compound"]),
    ("C3", [r"\bdesign\b", r"generat", r"de novo", r"propose\b.+\bmolecules?\b"]),
    ("C4", [r"novel", r"novelty", r"similar", r"analog", r"tanimoto"]),
    ("C5", [r"motif", r"sar", r"hinge", r"med.?chem", r"why.*work", r"pharmacophore"]),
    ("C6", [r"\b3d\b", r"visualize", r"mol\*", r"molstar", r"show.*(structure|pose|molecule)", r"pdb"]),
    ("C6D", [r"retrieve", r"dossier", r"structure of"]),
    ("C6P", [r"druggab", r"pocket", r"binding.?site"]),
    ("C7", [r"synthe", r"retrosynth", r"can.*(made|make)", r"route"]),
    ("C8", [r"export", r"report", r"trace", r"capture", r"explain"]),
]


# Unambiguous "render it" cues — these win over every other capability.
EXPLICIT_3D = r"\b3d\b|visuali[sz]|mol\*|molstar|\brender\b|\bviewer\b|\bpose\b"
# Phrasing that asks about the target itself rather than its picture.
TARGET_CUE = r"\btarget\b|tell me about|target profile|\buniprot\b|\bwhat (?:is|are)\b"
# Asking which structures exist is a target-intelligence question, not a render request.
STRUCTURE_QUERY = (
    r"crystal structure|available structure|structures?\s+(?:of|for|exist)"
    r"|list.*structure|how many structure|what structure|structures?\s+in the"
)
# A concrete entry id ("6VNE" / "3UGC").
PDB_ID = r"\b[0-9][a-z0-9]{3}\b"
POCKET_CUE = r"druggab|binding.?pocket|binding.?site|\bpockets?\b"
DOSSIER_CUE = r"\bretrieve\b|dossier|structure overview|pdb structure of|get (?:the )?pdb|fetch (?:the )?pdb"


def classify_intent(query: str) -> str:
    q = (query or "").lower()
    # Understand the protein and choose an approach before any generation or novelty screen.
    if _strategy_question(query) and not _opens_generation(query):
        return "CX"
    # Produce molecules only when the scientist asks for them now.
    if _opens_generation(query):
        return "C3"
    # Pocket / druggability before generic 3D
    if re.search(POCKET_CUE, q):
        return "C6P"
    if re.search(r"\bnovel|novelty|tanimoto|similar(?:ity)?\b", q):
        return "C4"
    if re.search(r"\bmotif|sar\b|hinge|pharmacophore|med.?chem", q):
        return "C5"
    if re.search(r"synthe|retrosynth|can.*(made|make)|route tree", q):
        return "C7"
    if re.search(r"\bexport\b|\breport\b|\btrace\b|\bcapture\b", q):
        return "C8"
    if is_scientific_explanation(query):
        return "EXPLAIN"
    if re.search(r"known.*(agonist|inhibitor|active|ligand)|(?<!p)chembl|show.*inhibitor|bioactive", q):
        return "C2"
    # Structure dossier for a named PDB entry
    if re.search(DOSSIER_CUE, q) and re.search(PDB_ID, q):
        return "C6D"
    if re.search(EXPLICIT_3D, q):
        return "C6"
    # Named PDB without "list structures" language → dossier
    if re.search(PDB_ID, q) and not re.search(STRUCTURE_QUERY, q) and not re.search(TARGET_CUE, q):
        if re.search(r"structure|pdb|complex|entry", q):
            return "C6D"
    # Questions about a target or which structures exist
    if re.search(TARGET_CUE, q) or (
        re.search(STRUCTURE_QUERY, q) and not re.search(r"structure of\s+" + PDB_ID, q)
    ):
        # "structure of 3UGC" is dossier; "structures of JAK2" is C1
        if re.search(r"structure of\s+" + PDB_ID, q):
            return "C6D"
        return "C1"
    # Weaker visualization phrasing only after target questions are ruled out.
    if re.search(r"show.*(structure|molecule)|\bpdb\b", q):
        return "C6"
    scores: dict[str, int] = {}
    for cap, patterns in INTENT_PATTERNS:
        for p in patterns:
            if re.search(p, q, re.I):
                scores[cap] = scores.get(cap, 0) + 1
    if not scores:
        return "CX"
    return max(scores.items(), key=lambda x: x[1])[0]


def _refers_to_thread(query: str) -> bool:
    return bool(re.search(
        r"\b(these|those|them|this thread|the (?:new )?molecules|candidates|"
        r"which|compare|the top|what about|tell me more|follow|among)\b",
        query or "",
        re.I,
    ))


def _strategy_question(query: str) -> bool:
    """Understand the protein and choose an approach before any molecules are made."""
    return bool(re.search(
        r"help me understand|binding strateg|understand the target|identify potential|"
        r"potential binding|before (?:any |we )?(?:design|generat)|atp[-\s]?competitive|allosteric",
        query or "",
        re.I,
    ))


def _opens_generation(query: str) -> bool:
    """A request to produce molecules now. Naming a design goal is not enough."""
    if _strategy_question(query) and not re.search(r"\b(generate|generation)\b|\bdesign\s+\d+", query or "", re.I):
        return False
    return bool(re.search(
        r"\b(generate|generation|de novo)\b|\bdesign\s+\d+|\bsmall molecules?\s+against\b|"
        r"\bpropose\b.+\bmolecules?\b|\bdesign\s+(?:a\s+)?(?:small\s+)?(?:set|molecules)\b",
        query or "",
        re.I,
    ))


def _explicit_design(query: str) -> bool:
    return _opens_generation(query)


def _named_variants(query: str) -> list[str]:
    seen: list[str] = []
    for match in re.finditer(r"\b([A-Z]\d{2,4}[A-Z])\b", query or ""):
        token = match.group(1)
        if token not in seen:
            seen.append(token)
    return seen


def _likeness_question(query: str) -> bool:
    return bool(re.search(
        r"look more like|more like|you just found|just found|already found|"
        r"compared with|\bversus\b|\brather than\b",
        query or "",
        re.I,
    ))


def _mentioned_pdb_ids(query: str) -> list[str]:
    seen: list[str] = []
    for match in re.finditer(r"\b([0-9][A-Za-z0-9]{3})\b", query or ""):
        pid = match.group(1).upper()
        if pid not in seen:
            seen.append(pid)
    return seen


def _continue_thread(query: str, session: dict) -> dict[str, Any]:
    """Answer from molecules already in this session. No new calculation."""
    target = session.get("target") or {}
    gene = target.get("gene_symbol")
    name = target.get("name") or gene
    pdb = session.get("last_pdb_id")
    structures = session.get("structures") or []
    actives = session.get("actives") or []
    candidates = session.get("candidates") or []
    question = (query or "").strip()
    lines: list[str] = []

    if name:
        lines.append(f"Staying on {name}.")
    else:
        lines.append("No protein has been chosen yet.")
    if gene and target.get("uniprot_id"):
        lines.append(f"It is {gene}, UniProt {target.get('uniprot_id')}.")
    if pdb:
        lines.append(f"The structure we are looking at is {pdb}.")
    structure_ids = [s.get("pdb_id") for s in structures[:5] if s.get("pdb_id")]
    if structure_ids:
        lines.append("Structures already retrieved: " + ", ".join(structure_ids) + ".")
    if actives:
        labels = [
            a.get("pref_name") or a.get("chembl_id")
            for a in actives[:4]
            if a.get("pref_name") or a.get("chembl_id")
        ]
        if labels:
            lines.append("Known active compounds already found: " + ", ".join(labels) + ".")
    ranked = sorted(
        [c for c in candidates if isinstance(c.get("qed"), (int, float))],
        key=lambda c: c["qed"],
        reverse=True,
    )
    named = ranked[:4] or candidates[:4]
    if named:
        bits = []
        for cand in named:
            qed = cand.get("qed")
            qed_bit = f", QED {qed}" if isinstance(qed, (int, float)) else ""
            bits.append(f"{cand.get('candidate_id')}{qed_bit}")
        lines.append("Molecules already proposed: " + "; ".join(bits) + ".")
        if ranked and re.search(r"which|best|top|compare|drug", question, re.I):
            top = ranked[0]
            lines.append(
                f"Among those, {top.get('candidate_id')} has the highest QED already stored"
                f" ({top.get('qed')}). That restates the design card."
            )
    if question:
        lines.append(f"You asked: “{question}”.")
    if not (name or structures or actives or candidates):
        lines.append("Name a protein, such as EGFR or the GLP-1 receptor, or a PDB entry, such as 6X1A. No default profile was opened.")
    elif not actives:
        lines.append(f"Known {gene or 'target'} inhibitors have not been looked up yet.")
    elif not candidates:
        lines.append(
            "Known actives are here."
            + (f" A design question can propose molecules against {pdb}." if pdb else " A design question can propose molecules against this target.")
        )
    else:
        lines.append("Ask about novelty, the motifs, or whether the top molecule can be made. A new design starts only when you ask to design.")

    narrative = " ".join(lines)
    summary = f"Continuing with {gene}" if gene else "Tell me which protein you want to study"
    return {
        "capability": "CX",
        "capability_name": "Conversation",
        "summary": summary,
        "narrative": narrative,
        "target": target or None,
        "tools_used": ["Session"],
        "parameters": {"session_id": session.get("id"), "question": question[:240]},
        "trace": _trace(
            "Thread",
            ["Session"],
            {"question": question[:240]},
            ["Answered from the molecules already in this session"],
        ),
    }


def _chat(query: str, session: dict) -> dict[str, Any]:
    """Answer a greeting or a question that is not about this session's calculations."""
    question = (query or "").strip()
    target = session.get("target") or {}
    name = target.get("name") or target.get("gene_symbol")
    reply = None
    called = False
    model_used = None
    try:
        from app.services.llm_service import llm_service
        from app.services.output_style import plain_reply

        model = _conversation_model()
        if model and llm_service.available:
            system = (
                "You are Molecular Discovery Studio, talking with one scientist. "
                "They are not asking you to run a calculation. Answer the message they actually sent. "
                "A greeting gets a greeting, not a project status report. "
                "A question outside this session gets a real, specific, concise answer. "
                "Be warm, sharp, and lightly witty. Two to five sentences. "
                "Do not invent potencies, docking scores, molecule names, database hits, or tool results. "
                "Do not claim that a search or a calculation ran. "
                + (
                    f"A protein is already open: {name}. You may mention it in one short clause. "
                    if name
                    else "No protein is open. If it fits, invite them to name one, such as EGFR or the GLP-1 receptor. "
                )
                + "No headings and no bullet lists."
            )
            prompt = f"Scientist: {question}"
            reply = llm_service.chat(system, prompt, model=model, temperature=0.6)
            model_used = model
            if not (reply and str(reply).strip()):
                alternate = _alternate_conversation_model(model)
                if alternate:
                    reply = llm_service.chat(system, prompt, model=alternate, temperature=0.6)
                    if reply and str(reply).strip():
                        model_used = alternate
            reply = plain_reply(str(reply or ""))
            called = bool(reply)
    except Exception:
        reply = None
        called = False
    if not called:
        greeting = bool(re.match(
            r"^(?:(?:well|oh|um|so|ok|okay)[, ]+)?(?:hi|hello|hey|hiya|howdy|yo|good\s+(?:morning|afternoon|evening)|thanks|thank you)\b",
            question,
            re.I,
        ))
        if greeting and name:
            reply = (
                f"Hello. {name} is still open, and saying hello did not run a search. "
                "Ask about its structures, its known ligands, or the molecules already designed — or ask me something else."
            )
        elif greeting:
            reply = (
                "Hello. I can talk, and I can also stay with one protein for a whole session. "
                "When you want to work, name one. EGFR and the GLP-1 receptor are both fair openings."
            )
        elif name:
            reply = (
                f"That is outside the {name} work, so I did not look anything up. "
                "Ask it as a general question and I will answer it, or ask me something about the protein already open."
            )
        else:
            reply = (
                "I can answer that as conversation. Nothing was searched, because you did not ask for a protein. "
                "Ask again in your own words, or name a protein and I will stay with it."
            )
    tools = ["LLM"] if called else ["Session"]
    return {
        "capability": "CHAT",
        "capability_name": "Conversation",
        "summary": f"Talking with you{f' while {name} stays open' if name else ''}.",
        "narrative": str(reply or "").strip()[:1600],
        "llm_called": called,
        "llm_model": model_used if called else None,
        "tools_used": tools,
        "parameters": {"session_id": session.get("id"), "question": question[:240]},
        "trace": _trace(
            "Conversation",
            tools,
            {"question": question[:240], "llm_called": called},
            ["Answered as conversation. No database and no calculation were run."],
        ),
    }


def _need_context(query: str) -> dict[str, Any]:
    question = (query or "").strip()
    narrative = (
        "Tell me which protein you want to study, or give me a PDB code. "
        "Nothing was looked up yet."
    )
    if question:
        narrative = f"“{question}” does not name a protein or a structure. {narrative}"
    return {
        "capability": "CONTEXT",
        "capability_name": "Choose a protein",
        "summary": "Tell me which protein you want to study.",
        "narrative": narrative,
        "needs_context": True,
        "tools_used": [],
        "parameters": {"query": question[:240]},
        "trace": _trace("Context", [], {"query": question[:240]}, ["No lookup. Context is not set."]),
    }


def _session_facts(session: dict) -> str:
    target = session.get("target") or {}
    lines: list[str] = []
    if target.get("gene_symbol"):
        lines.append(
            f"Protein: {target.get('name') or target.get('gene_symbol')} "
            f"({target.get('gene_symbol')}), UniProt {target.get('uniprot_id') or 'not recorded'}."
        )
        if target.get("function"):
            lines.append(f"Function already on file: {str(target.get('function'))[:300]}")
    if session.get("last_pdb_id"):
        lines.append(f"Open structure: {session.get('last_pdb_id')}.")
    titled = []
    for row in (session.get("structures") or [])[:8]:
        pid = row.get("pdb_id")
        if not pid:
            continue
        title = (row.get("title") or "").strip()
        titled.append(f"{pid} ({title})" if title else str(pid))
    if titled:
        lines.append("Structures already retrieved: " + "; ".join(titled) + ".")
    actives = session.get("actives") or []
    if actives:
        labels = [
            a.get("pref_name") or a.get("chembl_id")
            for a in actives[:6]
            if a.get("pref_name") or a.get("chembl_id")
        ]
        lines.append(f"Known actives already retrieved ({len(actives)}): " + ", ".join(labels) + ".")
    candidates = session.get("candidates") or []
    if candidates:
        bits = []
        for cand in candidates[:6]:
            qed = cand.get("qed")
            bits.append(
                f"{cand.get('candidate_id')}" + (f" QED {qed}" if isinstance(qed, (int, float)) else "")
            )
        lines.append(f"Generated molecules stored ({len(candidates)}): " + "; ".join(bits) + ".")
    selected = (session.get("selection") or {}).get("molecule_id")
    if selected:
        lines.append(f"The scientist has selected {selected}.")
    prior = [card.get("query") for card in (session.get("cards") or [])[-4:] if card.get("query")]
    if prior:
        lines.append("Recent questions: " + " | ".join(prior))
    return "\n".join(lines) or "No facts are stored yet."


def _is_peptide_like(smiles: str) -> bool:
    """A stored structure with many amide bonds is in the peptide class."""
    if not smiles:
        return False
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("unreadable")
        amide = Chem.MolFromSmarts("[NX3][CX3](=[OX1])[#6]")
        amides = len(mol.GetSubstructMatches(amide)) if amide is not None else 0
        return amides >= 6 or mol.GetNumHeavyAtoms() >= 80
    except Exception:
        return len(smiles) >= 250


def _display_name(item: dict) -> str:
    name = (item.get("pref_name") or "").strip()
    cid = (item.get("chembl_id") or "").strip()
    if name and name != cid:
        return name
    return cid or name


def _name_list(items: list[dict], limit: int = 4) -> str:
    names = [_display_name(item) for item in items if _display_name(item)]
    shown = names[:limit]
    extra = len(names) - len(shown)
    text = ", ".join(shown)
    if extra > 0:
        text += f", and {extra} more"
    return text


def _count(n: int, singular: str, plural: str | None = None) -> str:
    word = singular if n == 1 else (plural or f"{singular}s")
    return f"{n} {word}"


def _stored_number(value: Any, digits: int = 2) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{value:.{digits}f}"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{value:.{digits}f}"


def _peptide_title(title: str) -> bool:
    text = (title or "").lower()
    if "non-peptide" in text or "non peptide" in text:
        return False
    return "peptide" in text


def _small_title(title: str) -> bool:
    text = (title or "").lower()
    return any(word in text for word in ("non-peptide", "non peptide", "small molecule", "inhibitor", "agonist")) and not _peptide_title(title)


def _next_step(session: dict) -> str:
    gene = (session.get("target") or {}).get("gene_symbol") or "this protein"
    if not session.get("structures"):
        return f"Shall I look up crystal structures for {gene}?"
    if not session.get("actives"):
        return f"Shall I retrieve known compounds for {gene}?"
    if not session.get("candidates"):
        return f"Shall I design a small set of molecules for {gene}?"
    return "Shall I check whether the designed molecules are novel against the known compounds?"


def _session_conversation(query: str, session: dict, *, retrieved_now: bool = False) -> dict[str, Any] | None:
    """The same reply shape for every protein: stored facts, a short table, one next question."""
    target = session.get("target") or {}
    name = target.get("name") or target.get("gene_symbol")
    structures = session.get("structures") or []
    actives = session.get("actives") or []
    candidates = session.get("candidates") or []
    if not name and not structures and not actives and not candidates:
        return None
    by_id = {str(row.get("pdb_id") or "").upper(): row for row in structures}
    mentioned = _mentioned_pdb_ids(query)
    named_rows = [(pid, by_id.get(pid) or {}) for pid in mentioned]
    peptide_ref = next((pid for pid, row in named_rows if _peptide_title(row.get("title") or "")), None)
    small_ref = next((pid for pid, row in named_rows if _small_title(row.get("title") or "")), None)
    paragraphs: list[str] = []
    if name:
        paragraphs.append(f"Staying with {name}.")
    structure_bits = []
    for pid, row in named_rows:
        title = (row.get("title") or "").strip()
        structure_bits.append(f"{pid} is {title}." if title else f"{pid} is not among the structures stored here.")
    if structure_bits:
        paragraphs.append(" ".join(structure_bits))
    elif structures:
        sample = []
        for row in structures[:3]:
            pid = row.get("pdb_id")
            title = (row.get("title") or "").strip()
            if pid and title:
                sample.append(f"{pid} ({title})")
            elif pid:
                sample.append(str(pid))
        if sample:
            paragraphs.append(
                f"{len(structures)} structures are stored for this protein, including " + "; ".join(sample) + "."
            )

    peptides = [item for item in actives if _is_peptide_like(item.get("smiles") or "")]
    smaller_actives = [item for item in actives if item not in peptides]
    rows: list[dict[str, str]] = []
    comparing = _likeness_question(query)
    if _strategy_question(query) and not _opens_generation(query):
        variants = _named_variants(query)
        paragraphs: list[str] = []
        if name:
            paragraphs.append(f"Staying with {name}.")
        record_bits = []
        if target.get("uniprot_id"):
            record_bits.append(f"The protein record is UniProt {target.get('uniprot_id')}")
            count = target.get("structure_count")
            if isinstance(count, int) and count > 0:
                record_bits.append(f"{_count(count, 'structure')} {'is' if count == 1 else 'are'} recorded for it")
        if record_bits:
            paragraphs.append(". ".join(record_bits) + ".")
        elif name:
            paragraphs.append("The protein record has not been retrieved yet.")
        if variants:
            paragraphs.append(
                "You named " + ", ".join(variants) + ". "
                "Those variants are not separated in the structures stored so far."
            )
        if session.get("candidates"):
            paragraphs.append(
                f"{_count(len(session['candidates']), 'molecule')} already designed in this work. "
                "A binding strategy for a new series has not been chosen. "
                "Shall we explore the ATP site, or an allosteric site?"
            )
        else:
            paragraphs.append(
                "No binding strategy has been chosen, and no molecules have been designed. "
                "Shall we explore the ATP site, or an allosteric site?"
            )
        return {
            "summary": f"Staying with {name}. No molecules have been designed yet." if name else paragraphs[0],
            "narrative": "\n\n".join(paragraphs[1:] if paragraphs and paragraphs[0].startswith("Staying with") else paragraphs),
            "review": None,
        }

    if actives:
        source = "I retrieved" if retrieved_now else "This work already has"
        if peptides and not smaller_actives:
            kind = "It is a long peptide" if len(actives) == 1 else "They are long peptides"
            sentence = f"{source} {_count(len(actives), 'known compound')}. {kind}"
            if comparing and peptide_ref:
                sentence += f", the same class as the structure {peptide_ref}"
            sentence += "."
            if comparing and small_ref:
                none = "It is not" if len(actives) == 1 else "None of them is"
                sentence += f" {none} a smaller molecule like the ligand in {small_ref}."
            paragraphs.append(sentence)
        elif smaller_actives and not peptides:
            kind = "It is a smaller molecule" if len(actives) == 1 else "They are smaller molecules"
            sentence = f"{source} {_count(len(actives), 'known compound')}. {kind}"
            if comparing and small_ref:
                sentence += f", the same class as the ligand in {small_ref}"
            sentence += "."
            paragraphs.append(sentence)
        else:
            paragraphs.append(
                f"{source} {len(actives)} known compounds. "
                f"{len(peptides)} are long peptides and {len(smaller_actives)} are smaller molecules."
            )
        ranked = sorted(actives, key=lambda item: item.get("pchembl") or 0, reverse=True)
        for item in ranked[:3]:
            pchembl = _stored_number(item.get("pchembl"))
            kind = "Peptide" if item in peptides else "Smaller molecule"
            rows.append({
                "group": "Known compounds",
                "example": _display_name(item),
                "record": f"{kind}, pChEMBL {pchembl}" if pchembl else kind,
            })
    elif comparing:
        paragraphs.append("Known compounds have not been retrieved for this protein yet.")

    if candidates:
        ranked_candidates = sorted(
            candidates,
            key=lambda item: item.get("qed") if isinstance(item.get("qed"), (int, float)) else -1,
            reverse=True,
        )
        top = ranked_candidates[0]
        qed = _stored_number(top.get("qed"), 3)
        qed_bit = f" The highest stored QED is {qed} on {top.get('candidate_id')}." if qed and top.get("candidate_id") else ""
        if len(candidates) == 1:
            designed = "The molecule designed in this work is a smaller structure." + qed_bit
        else:
            designed = (
                f"The {len(candidates)} molecules designed in this work are smaller structures."
                + qed_bit
            )
        if comparing and small_ref:
            designed += f" That is the set that belongs with {small_ref}."
        paragraphs.append(designed)
        for item in ranked_candidates[:2]:
            qed = _stored_number(item.get("qed"), 3)
            rows.append({
                "group": "Designed molecules",
                "example": item.get("candidate_id") or "Candidate",
                "record": f"QED {qed}" if qed else "Designed in this work",
            })
    elif comparing and actives:
        paragraphs.append("No molecules have been designed in this work yet.")

    paragraphs.append(_next_step(session))
    if actives and peptides and not smaller_actives and candidates:
        summary = f"The known compounds for {name or 'this protein'} are long peptides. The designed molecules are the smaller set."
    elif actives and smaller_actives and not peptides and candidates:
        summary = f"The known compounds and the designed molecules for {name or 'this protein'} are both smaller molecules."
    elif name:
        summary = f"Staying with {name}."
    else:
        summary = paragraphs[0]
    body = paragraphs[1:] if summary == paragraphs[0] else paragraphs
    return {
        "summary": summary,
        "narrative": "\n\n".join(body),
        "review": {
            "title": "What is already stored",
            "note": "These values come from the records already in this work.",
            "rows": rows,
        } if rows else None,
    }


def _asks_novelty(query: str) -> bool:
    return bool(re.search(r"\b(novel|novelty|tanimoto|similar(?:ity)?)\b", query or "", re.I))


_INVENTED_CAVEATS = (
    re.compile(r"patent|freedom-to-operate|freedom to operate", re.I),
    re.compile(r"like-for-like|like for like", re.I),
    re.compile(r"binding affinit|kinetic parameter", re.I),
    re.compile(r"not measured|were not measured|was not measured", re.I),
)
_PMID = re.compile(r"(?:pubmed|pmid)\s*:?\s*(\d{6,9})", re.I)


def _drop_invented_caveats(source: str, reply: str) -> str:
    """A structure lookup must not grow novelty, patent, or affinity caveats."""
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", (reply or "").strip()):
        if not sentence:
            continue
        invented = any(topic.search(sentence) and not topic.search(source or "") for topic in _INVENTED_CAVEATS)
        cited = set(_PMID.findall(sentence))
        if cited and not cited <= set(_PMID.findall(source or "")):
            invented = True
        if not invented:
            kept.append(sentence)
    return " ".join(kept).strip()


def _drug_lookup_missed(query: str, result: dict[str, Any], session: dict[str, Any]) -> bool:
    """ChEMBL returned no activities, and the question still names a protein."""
    if result.get("capability") != "C2" or result.get("actives"):
        return False
    gene = extract_gene_symbol(query) or (session.get("target") or {}).get("gene_symbol")
    return bool(gene)


def _answer_when_lookup_misses(query: str, session: dict[str, Any]) -> str | None:
    """OpenAI answers only after the drug lookup failed. The reply is labeled as model knowledge."""
    gene = extract_gene_symbol(query) or (session.get("target") or {}).get("gene_symbol") or "this protein"
    try:
        from app.services.llm_service import llm_service
        from app.services.output_style import plain_reply

        model = _conversation_model()
        if not model or not llm_service.available:
            return None
        system = (
            "You are a medicinal chemist in Molecular Discovery Studio. "
            "ChEMBL did not return activities for this question, so answer from general knowledge. "
            f"The protein is {gene}. Do not substitute a different gene, including one that differs by a single letter. "
            "Name drugs or clinical candidates you are confident about. "
            "Do not invent pChEMBL values, assay identifiers, docking scores, or ADMET numbers. "
            "Do not say that a database lookup succeeded. "
            "Write three to six plain sentences. No headings and no bullet lists."
        )
        reply = llm_service.chat(system, f"Scientist: {(query or '').strip()[:500]}", model=model, temperature=0.3)
        if not (reply and str(reply).strip()):
            alternate = _alternate_conversation_model(model)
            if alternate:
                reply = llm_service.chat(
                    system, f"Scientist: {(query or '').strip()[:500]}", model=alternate, temperature=0.3
                )
        text = plain_reply(str(reply or ""))
        if not text:
            return None
        return (
            f"ChEMBL did not return activities for {gene} in this turn. "
            "This answer is from the language model, not from that lookup. "
            + text
        )
    except Exception:
        return None


def _speak(query: str, result: dict[str, Any]) -> str | None:
    """Phrase a finished tool result as a reply. The tool text stays the record."""
    narrative = (result.get("narrative") or "").strip()
    if not narrative or result.get("capability") in {"EXPLAIN", "PRECONDITION", "CX", "CHAT", "ROLE"}:
        return None
    try:
        from app.services.llm_service import llm_service
        from app.services.output_style import plain_reply

        model = _conversation_model()
        if not model or not llm_service.available:
            return None
        system = (
            "You are a medicinal chemist replying to one scientist in Molecular Discovery Studio. "
            "Rewrite the tool result as your own reply to the question they just asked. "
            "Use only facts written in the tool result. Keep its counts, names, and identifiers. "
            "Do not add a patent assessment, a like-for-like comparison, a binding affinity, "
            "or a statement that something was not measured, unless that exact caveat is written in the tool result. "
            "Write three to six plain sentences and end with one useful next question. "
            "No headings, no capability codes, and no bullet lists."
        )
        prompt = f"Scientist: {(query or '').strip()[:500]}\n\nTool result:\n{narrative[:4000]}"
        reply = llm_service.chat(system, prompt, model=model, temperature=0.3)
        if not (reply and str(reply).strip()):
            alternate = _alternate_conversation_model(model)
            if alternate:
                reply = llm_service.chat(system, prompt, model=alternate, temperature=0.3)
        reply = _drop_invented_caveats(narrative, plain_reply(str(reply or "")))
        return reply[:1600] or None
    except Exception:
        return None


def _conversation_model() -> str | None:
    """OpenAI on a Mac or an Azure VM. Bedrock on EC2, where that provider is selected."""
    import platform

    from app.config import settings
    from app.services.llm_service import is_bedrock_llm_model, is_openai_model, llm_service

    cloud = (settings.scinova_cloud or "").strip().lower()
    prefer_openai = cloud in {"azure", "local"} or platform.system() == "Darwin"
    if prefer_openai and llm_service.openai_available:
        model = settings.llm_model
        return model if is_openai_model(model) else "gpt-4o-mini"
    on_aws = cloud == "aws" or (cloud == "" and platform.system() != "Darwin")
    bedrock_selected = (
        settings.bedrock_enabled
        or (settings.default_llm_provider or "").strip().lower() == "bedrock"
        or is_bedrock_llm_model(settings.llm_model)
    )
    if on_aws and bedrock_selected and llm_service.bedrock_available:
        return settings.bedrock_llm_model or settings.llm_model
    if llm_service.is_configured(settings.llm_model):
        return settings.llm_model
    if llm_service.openai_available:
        return "gpt-4o-mini"
    if llm_service.bedrock_available:
        return settings.bedrock_llm_model or None
    return None


def _alternate_conversation_model(used: str | None) -> str | None:
    from app.config import settings
    from app.services.llm_service import is_openai_model, llm_service

    if used and is_openai_model(used) and llm_service.bedrock_available:
        alt = settings.bedrock_llm_model or settings.llm_model
        if alt and alt != used:
            return alt
    if used and not is_openai_model(used) and llm_service.openai_available:
        alt = settings.llm_model if is_openai_model(settings.llm_model) else "gpt-4o-mini"
        if alt != used:
            return alt
    return None


def _label_for_smiles(smiles: str | None, actives: list[dict]) -> str:
    if not smiles:
        return "a stored known compound"
    for item in actives:
        if item.get("smiles") and item.get("smiles") == smiles:
            return _display_name(item)
    return "a stored known compound"


def _conversation_facts(session: dict, novelty_rows: list[dict] | None, *, asked_novelty: bool) -> str:
    lines = [_session_facts(session)]
    actives = session.get("actives") or []
    candidates = session.get("candidates") or []
    if actives:
        peptides = [item for item in actives if _is_peptide_like(item.get("smiles") or "")]
        smaller = [item for item in actives if item not in peptides]
        lines.append(
            f"Known-compound classes from stored structures: {_count(len(peptides), 'long peptide')}, "
            f"{_count(len(smaller), 'smaller molecule')}."
        )
        ranked = sorted(actives, key=lambda item: item.get("pchembl") or 0, reverse=True)
        bits = []
        for item in ranked[:5]:
            pchembl = _stored_number(item.get("pchembl"))
            bits.append(
                f"{_display_name(item)}" + (f" pChEMBL {pchembl}" if pchembl else "")
            )
        if bits:
            lines.append("Strongest stored potencies: " + "; ".join(bits) + ".")
    if candidates:
        lines.append(f"Designed molecules stored: {_count(len(candidates), 'molecule')}.")
    if novelty_rows:
        lines.append(
            "Similarity was calculated in this turn against the known compounds stored here "
            "(Morgan fingerprint, radius 2). Use these values and no others:"
        )
        for row in novelty_rows:
            nearest = _label_for_smiles(row.get("closest_analog_smiles"), actives)
            lines.append(
                f"- {row.get('candidate_id')}: Tanimoto {row.get('max_tanimoto')}, "
                f"{row.get('novelty_label')}, nearest {nearest}."
            )
    elif asked_novelty:
        lines.append("Similarity against the known compounds has not been calculated. Do not estimate one.")
    history = []
    for card in (session.get("cards") or [])[-3:]:
        question = (card.get("query") or "").strip()
        answer = (card.get("narrative") or card.get("summary") or "").strip()
        if question:
            history.append(f"Scientist: {question[:240]}\nStudio: {answer[:500]}")
    if history:
        lines.append("Conversation so far:\n" + "\n".join(history))
    return "\n".join(lines)


def _converse(query: str, session: dict, *, retrieved_now: bool = False) -> dict[str, Any]:
    """Talk from the session. The model phrases the reply. Numbers come from the record."""
    question = (query or "").strip()
    novelty_rows: list[dict] = []
    if _asks_novelty(question):
        candidates = session.get("candidates") or []
        actives = session.get("actives") or []
        if candidates and actives:
            assessed = assess_novelty(candidates, actives)
            novelty_rows = assessed.get("novelty") or []
            if session.get("id") and novelty_rows:
                session_store.update_session(session["id"], novelty=novelty_rows)
                session["novelty"] = novelty_rows
    facts = _conversation_facts(session, novelty_rows or None, asked_novelty=_asks_novelty(question))
    reply = None
    called = False
    model_used = None
    try:
        from app.services.llm_service import llm_service
        from app.services.output_style import plain_reply

        model = _conversation_model()
        if model and llm_service.available:
            system = (
                "You are a medicinal chemist talking with one scientist in Molecular Discovery Studio. "
                "The protein has already been chosen. Stay with it. "
                "Answer the question they just asked. "
                "Use only the session record for identifiers, counts, potencies, QED, structure titles, and similarities. "
                "When a similarity block is present, the comparison has been run. Discuss those values. "
                "When it is absent, say the comparison has not been calculated. Do not estimate a similarity. "
                "Do not invent potencies, docking scores, selectivity, pocket measurements, or molecule names. "
                "A long peptide and a smaller designed molecule are different classes. Say that only when the record says so. "
                "Do not start a new design unless they asked to design molecules now. "
                "Write three to six plain sentences and end with one next question. No headings and no bullet lists."
            )
            reply = llm_service.chat(system, f"Session record:\n{facts}\n\nScientist: {question}", model=model, temperature=0.3)
            model_used = model
            if not (reply and str(reply).strip()):
                alternate = _alternate_conversation_model(model)
                if alternate:
                    reply = llm_service.chat(
                        system,
                        f"Session record:\n{facts}\n\nScientist: {question}",
                        model=alternate,
                        temperature=0.3,
                    )
                    if reply and str(reply).strip():
                        model_used = alternate
            reply = plain_reply(str(reply or ""))
            called = bool(reply)
    except Exception:
        reply = None
        called = False
    grounded = _session_conversation(question, session, retrieved_now=retrieved_now)
    review = None
    if novelty_rows:
        review = {
            "title": "Designed molecules against the known compounds",
            "note": "Morgan fingerprint, radius 2, compared with the known compounds stored in this work.",
            "rows": [
                {
                    "group": "Designed vs known",
                    "example": row.get("candidate_id") or "Candidate",
                    "record": (
                        f"Tanimoto {row.get('max_tanimoto')}, {row.get('novelty_label')}, "
                        f"nearest {_label_for_smiles(row.get('closest_analog_smiles'), session.get('actives') or [])}"
                    ),
                }
                for row in novelty_rows[:8]
            ],
        }
    elif grounded and grounded.get("review"):
        review = grounded["review"]
    if not called:
        reply = (grounded or {}).get("narrative") or _continue_thread(question, session).get("narrative")
    reply = str(reply or "").strip()[:1600]
    gene = (session.get("target") or {}).get("gene_symbol")
    name = (session.get("target") or {}).get("name") or gene
    if novelty_rows:
        summary = (
            f"Compared {_count(len(novelty_rows), 'designed molecule')} with "
            f"{_count(len(session.get('actives') or []), 'known compound')} for {name or 'this protein'}."
        )
    elif name:
        summary = f"Staying with {name}."
    else:
        summary = "Continuing this conversation"
    if summary == reply:
        summary = f"Staying with {name}." if name else "Continuing this conversation"
    tools = ["Session"]
    if novelty_rows:
        tools.append("RDKit")
    if called:
        tools.append("LLM")
    return {
        "capability": "CX",
        "capability_name": "Conversation",
        "summary": summary,
        "narrative": reply,
        "review": review,
        "llm_called": called,
        "llm_model": model_used if called else None,
        "tools_used": tools,
        "parameters": {"session_id": session.get("id"), "question": question[:240], "gene": gene},
        "trace": _trace(
            "Conversation",
            tools,
            {"question": question[:240], "llm_called": called, "llm_model": model_used if called else None},
            [
                (
                    f"Answered from the stored {name or 'protein'} record"
                    + (f" with {len(novelty_rows)} similarity rows" if novelty_rows else "")
                ),
                "Model phrased the reply" if called else "Model unavailable; replied from the stored record",
            ],
        ),
    }


_SMILES_TOKEN = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#$%/\\.]+$")


def _looks_like_smiles(tok: str) -> bool:
    """Reject ordinary English words so plain prose is never depicted as a molecule."""
    if len(tok) < 6 or not _SMILES_TOKEN.match(tok):
        return False
    if tok.isalpha():
        # "structures", "Compound" — words, not structures.
        if tok.islower() or (tok[:1].isupper() and tok[1:].islower()):
            return False
    return bool(re.search(r"[=#\[\]()]", tok) or re.search(r"[CNOSPF]", tok))


def _trace(specialist: str, tools: list[str], parameters: dict, observations: list[str]) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "specialist": specialist,
        "tools": tools,
        "parameters": parameters,
        "observations": observations,
    }


def run_chem_query(
    query: str,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    intent_override: str | None = None,
    selected_molecule_id: str | None = None,
) -> dict[str, Any]:
    session = session_store.ensure_session(session_id, user_id)
    sid = session["id"]
    if selected_molecule_id:
        selection = dict(session.get("selection") or {})
        selection["molecule_id"] = selected_molecule_id
        session_store.update_session(sid, selection=selection)
        session = session_store.get_session(sid) or session

    orchestrator = ScientificConversationOrchestrator()
    if intent_override:
        plan: dict[str, Any] = {
            "capability": intent_override,
            "halt": None,
            "classification": {"primaryIntent": intent_override},
        }
    else:
        plan = orchestrator.plan(query, session, selected_molecule_id=selected_molecule_id)
        session_store.update_session(
            sid,
            research=session.get("research"),
            workflows=session.get("workflows"),
            selection=session.get("selection"),
        )
        session = session_store.get_session(sid) or session

    intent = plan.get("capability") or "CX"
    if is_scientific_explanation(query) and not intent_override:
        intent = "EXPLAIN"
        if plan.get("halt") is None:
            from app.services.chem.scientific_turn import explanation_result

            plan = {**plan, "halt": explanation_result(query), "capability": "EXPLAIN"}
    subject_gene = extract_gene_symbol(query)
    subject_pdb = extract_pdb_id(query)
    has_context = bool((session.get("target") or {}).get("gene_symbol") or session.get("last_pdb_id"))
    _ = has_context, subject_pdb

    # A named protein becomes the context before a later tool, or before a strategy conversation.
    needs_protein = (
        not plan.get("halt")
        and subject_gene
        and not (session.get("target") or {}).get("gene_symbol")
    )
    if needs_protein and (intent not in {"C1", "CONTEXT", "CHAT"} or _strategy_question(query)):
        boot = build_target_profile(query)
        if boot.get("target"):
            remembered = dict(boot["target"])
            if isinstance(boot.get("structure_count"), int):
                remembered["structure_count"] = boot["structure_count"]
            updates = {
                "target": remembered,
                "structures": boot["structures"],
            }
            # A strategy question names the protein. It does not choose a structure or a pocket.
            if not _strategy_question(query):
                updates["last_pdb_id"] = boot.get("default_pdb_id")
            session_store.update_session(sid, **updates)
            session = session_store.get_session(sid) or session

    result: dict[str, Any]

    if plan.get("halt"):
        result = plan["halt"]
        intent = result.get("capability") or intent
        result["trace"] = _trace(
            (plan.get("classification") or {}).get("specialist")
            or ("Scientific explanation" if intent == "EXPLAIN" else "Scientific prerequisite"),
            result.get("tools_used") or ["Session"],
            result.get("parameters") or {},
            [result.get("summary") or "No tool was run"],
        )

    elif intent == "CONTEXT":
        result = _need_context(query)

    elif intent == "CHAT":
        result = _chat(query, session)

    elif intent == "CX":
        retrieved_now = False
        target = session.get("target") or {}
        asks_for_compounds = re.search(r"\b(retrieve|show|find|fetch)\b.+\b(compound|inhibitor|active|ligand)", query, re.I)
        if (
            asks_for_compounds
            and not _asks_novelty(query)
            and not is_scientific_explanation(query)
            and not (session.get("actives") or [])
            and target.get("uniprot_id")
        ):
            found = discover_known_actives(target.get("uniprot_id"), target.get("gene_symbol"))
            if found.get("actives"):
                session_store.update_session(sid, actives=found["actives"])
                session = session_store.get_session(sid) or session
                retrieved_now = True
        result = _converse(query, session, retrieved_now=retrieved_now)

    elif intent == "ROLE":
        result = biological_role(query, session)
        if result.get("target") and not (session.get("target") or {}).get("gene_symbol"):
            session_store.update_session(sid, target=result["target"])
        result["trace"] = _trace(
            "Pathway Insight",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [result.get("summary") or "UniProt function comment"],
        )

    elif intent == "C1":
        result = build_target_profile(query)
        if result.get("target"):
            from datetime import datetime, timezone

            result["provenance"] = {
                "source": "UniProt and RCSB PDB",
                "status": "completed",
                "evidence": "measured",
                "tool": "UniProt, RCSB PDB",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "record_id": (result.get("target") or {}).get("uniprot_id"),
            }
            previous = (session.get("target") or {}).get("gene_symbol")
            opened = (result.get("target") or {}).get("gene_symbol")
            switched = bool(previous and opened and previous.upper() != opened.upper())
            updates = {
                "target": result["target"],
                "structures": result["structures"],
                "last_pdb_id": result.get("default_pdb_id"),
            }
            if switched:
                updates.update({
                    "actives": [],
                    "candidates": [],
                    "novelty": [],
                    "last_smiles": "",
                    "selection": {},
                })
                result["narrative"] = (
                    f"Switched from {previous} to {opened}. "
                    "Ligands and designed molecules from the previous protein were set aside. "
                    + (result.get("narrative") or "")
                )
                result["summary"] = f"Now studying {opened}. " + (result.get("summary") or "")
            session_store.update_session(sid, **updates)
        named = result.get("target") or {}
        result["trace"] = _trace(
            "Target Intelligence",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"Resolved {named.get('gene_symbol')} → {named.get('uniprot_id')}",
                f"{result.get('structure_count') or len(result.get('structures') or [])} PDB structures "
                f"(showing {len(result.get('structures') or [])})",
            ],
        )

    elif intent == "C2":
        target = session.get("target") or {}
        if not target.get("uniprot_id"):
            result = {
                "capability": "C2",
                "capability_name": "Known Bioactive Discovery",
                "summary": "No protein is open, so ChEMBL was not searched.",
                "narrative": (
                    "No protein is open in this session, so I did not search ChEMBL for drugs. "
                    "Name a gene, such as KRAS or EGFR, and ask again."
                ),
                "actives": [],
                "tools_used": ["Session"],
                "parameters": {},
                "provenance": {"kind": "lookup", "status": "not_run", "evidence": "not_run", "tool": "ChEMBL"},
            }
        else:
            result = discover_known_actives(
                target.get("uniprot_id"),
                target.get("gene_symbol"),
                modality=(plan.get("classification") or {}).get("modality"),
            )
        if result.get("actives"):
            result["actives"] = structure_identity_for_actives(result["actives"])
            if result.get("source") == "demo_curated":
                result["narrative"] = (
                    (result.get("narrative") or "")
                    + " Demo mode is on. These rows are illustrative and are excluded from novelty comparisons."
                )
            session_store.update_session(sid, actives=result["actives"])
            top = result["actives"][0]
            session_store.update_session(sid, last_smiles=top.get("smiles"))
        result["trace"] = _trace(
            "Known Bioactive Discovery",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [f"{len(result['actives'])} actives from {result.get('source')}"],
        )

    elif intent == "C3":
        target = session.get("target") or {}
        refs = [a.get("smiles") for a in reference_actives(session)[:5]]
        pdb_id = extract_pdb_id(query) or session.get("last_pdb_id")
        receptor_based = bool(
            pdb_id
            or re.search(r"against|receptor|pocket|rbdd|cvae|dock", query, re.I)
        )
        # Parse an explicit count. "20 candidates" and "8 molecules" are both requests.
        max_n = int(plan.get("generation_count") or 12)
        m_n = re.search(r"\b(\d+)\s+(?:small\s+)?(?:molecules?|candidates?)\b", query, re.I)
        if m_n:
            max_n = int(m_n.group(1))
        max_n = max(1, min(max_n, 50))
        pocket_id = "P_0"
        m_p = re.search(r"\b(P_\d+(?:_\d+)?)\b", query, re.I)
        if m_p:
            pocket_id = m_p.group(1).upper()
            if pocket_id.startswith("P") and not pocket_id.startswith("P_"):
                pocket_id = "P_" + pocket_id[1:]
        m_p2 = re.search(r"\bpocket\s*[:=]?\s*(P_[\w]+)", query, re.I)
        if m_p2:
            pocket_id = m_p2.group(1).upper()

        result = design_candidates(
            target.get("gene_symbol"),
            reference_smiles=refs,
            max_candidates=max_n,
            pdb_id=pdb_id,
            pocket_id=pocket_id if receptor_based else None,
            receptor_based=receptor_based,
        )
        kept = accept_generated(result)
        engine_rows = [
            row for row in (result.get("candidates") or [])
            if row.get("origin") in {"neural_analog", "neural_smiles_rnn", "lead_optimization"}
        ]
        if not kept:
            rdkit_ready = True
            try:
                import rdkit  # noqa: F401
            except ImportError:
                rdkit_ready = False
            reason = "rdkit" if engine_rows and not rdkit_ready else None
            result = generation_failure(target.get("gene_symbol"), max_n, reason=reason)
        else:
            dropped = len(result.get("candidates") or []) - len(kept)
            result["candidates"] = kept
            result["neural_count"] = len(kept)
            note = ""
            if dropped:
                note = f" {dropped} scaffold placeholders were discarded and not stored."
            result["summary"] = (
                f"The generation engine returned {len(kept)} validated molecules"
                + (f" for {target.get('gene_symbol')}" if target.get("gene_symbol") else "")
                + "."
            )
            result["narrative"] = (result.get("narrative") or result["summary"]) + note
            result["provenance"] = {
                "kind": "generation",
                "status": "completed",
                "evidence": "generated",
                "tool": "SMILES Char-RNN",
                "source": "smiles_char_rnn",
                "model": (result.get("generator") or {}).get("name"),
            }
        waiting = pending_generation(session)
        if waiting:
            transition(
                session,
                waiting["workflow_id"],
                "COMPLETED" if kept else "FAILED",
                note=result.get("summary"),
                error=None if kept else result.get("summary"),
            )
            session_store.update_session(
                sid,
                workflows=session.get("workflows"),
                research=session.get("research"),
            )
        if kept:
            session_store.update_session(sid, candidates=kept)
        if pdb_id:
            session_store.update_session(sid, last_pdb_id=pdb_id)
        if kept:
            session_store.update_session(sid, last_smiles=kept[0]["smiles"])
        result["trace"] = _trace(
            "Molecule Design",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [result.get("summary") or "Generation finished"],
        )

    elif intent == "C6D":
        pdb_id = extract_pdb_id(query) or session.get("last_pdb_id")
        result = build_structure_dossier(pdb_id, query)
        if result.get("pdb_id"):
            session_store.update_session(sid, last_pdb_id=result["pdb_id"])
        result["trace"] = _trace(
            "Structure Dossier",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"PDB={result.get('pdb_id')}",
                f"{len(result.get('ligands') or [])} ligands",
                f"Resolution={ (result.get('dossier') or {}).get('resolution') }",
            ],
        )

    elif intent == "C6P":
        pdb_id = extract_pdb_id(query) or session.get("last_pdb_id")
        result = analyze_pockets(pdb_id, query)
        if result.get("pdb_id"):
            session_store.update_session(sid, last_pdb_id=result["pdb_id"])
            session_store.update_session(sid, last_pocket=result.get("top_pocket"))
        result["trace"] = _trace(
            "Pocket / Druggability",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"PDB={result.get('pdb_id')}",
                f"{len(result.get('pockets') or [])} pockets",
                f"Top score={(result.get('top_pocket') or {}).get('druggability_score')}",
            ],
        )

    elif intent == "C4":
        cands = designed_molecules(session)
        acts = reference_actives(session)
        if not cands or not acts:
            from app.services.chem.scientific_turn import novelty_precondition

            result = novelty_precondition(
                "Are the designed molecules novel versus the known ligands?",
                session,
            ) or {
                "capability": "PRECONDITION",
                "summary": "Novelty was not calculated.",
                "narrative": "The comparison inputs are incomplete, so no similarity was calculated.",
                "tools_used": ["Session"],
            }
        else:
            result = assess_novelty(cands, acts)
            session_store.update_session(sid, novelty=result["novelty"])
        result["trace"] = _trace(
            "Novelty Assessment",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [result.get("summary") or "Novelty was not calculated"],
        )

    elif intent == "C5":
        cands = designed_molecules(session) or reference_actives(session)
        if not cands:
            result = {
                "capability": "PRECONDITION",
                "capability_name": "Scientific prerequisite",
                "summary": "SAR reasoning needs stored structures.",
                "narrative": "No generated molecules and no retrieved ligands are available, so no motif analysis was run.",
                "tools_used": ["Session"],
                "provenance": {"kind": "precondition", "status": "not_run", "evidence": "not_run"},
            }
        else:
            target = session.get("target") or {}
            result = reason_motifs(target.get("gene_symbol"), cands)
            session_store.update_session(sid, motifs=result)
        result["trace"] = _trace(
            "Med-Chem Reasoning",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [result.get("summary") or "Motif analysis was not run"],
        )

    elif intent == "C6":
        pdb_id = session.get("last_pdb_id")
        smiles = session.get("last_smiles")
        m = re.search(r"\b([0-9][A-Za-z0-9]{3})\b", query)
        if m:
            pdb_id = m.group(1).upper()
            session_store.update_session(sid, last_pdb_id=pdb_id)
        for tok in query.split():
            if _looks_like_smiles(tok):
                smiles = tok
                session_store.update_session(sid, last_smiles=smiles)
                break
        if not pdb_id and session.get("structures"):
            pdb_id = session["structures"][0].get("pdb_id")
        if not smiles and session.get("candidates"):
            smiles = session["candidates"][0].get("smiles")
        elif not smiles and session.get("actives"):
            smiles = session["actives"][0].get("smiles")
        result = build_visualization_payload(pdb_id=pdb_id, smiles=smiles)

        docking = None
        if smiles and re.search(r"dock|pose|shape", query, re.I):
            try:
                from app.services.docking_service import shape_similarity_screen

                library = []
                for a in (session.get("actives") or [])[:12]:
                    if a.get("smiles"):
                        library.append({"compound_id": a.get("chembl_id") or a.get("pref_name"), "smiles": a["smiles"]})
                for c in (session.get("candidates") or [])[:12]:
                    if c.get("smiles"):
                        library.append({"compound_id": c.get("candidate_id"), "smiles": c["smiles"]})
                if library:
                    hits = shape_similarity_screen(smiles, library, top_k=5)
                    if hits:
                        docking = {
                            "method": "rdkit_shape",
                            "query_smiles": smiles,
                            "hits": hits,
                            "note": "Shape-similarity pose ranking; load receptor in Mol* via PDB.",
                        }
            except Exception:
                docking = None
        if docking:
            result["docking"] = docking
            result["summary"] = (result.get("summary") or "") + f" Shape screen: {len(docking['hits'])} pose analogs."
            tools = list(result.get("tools_used") or [])
            if "RDKit Shape" not in tools:
                tools.append("RDKit Shape")
            result["tools_used"] = tools

        # Shallow copy for visualization slot (avoid circular JSON)
        result["visualization"] = {
            "pdb_id": result.get("pdb_id"),
            "smiles": result.get("smiles"),
            "file_url": result.get("file_url"),
            "viewer_url": result.get("viewer_url"),
            "assets": result.get("assets"),
            "controls": result.get("controls"),
        }
        result["trace"] = _trace(
            "Molecular Visualization",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"PDB={pdb_id or 'none'}",
                f"SMILES={'yes' if smiles else 'no'}",
                "Mol* interactive viewer ready",
                *(["Docking/shape hits attached"] if docking else []),
            ],
        )

    elif intent == "C7":
        smiles = session.get("last_smiles")
        cid = None
        if session.get("candidates"):
            smiles = smiles or session["candidates"][0].get("smiles")
            cid = session["candidates"][0].get("candidate_id")
        elif session.get("actives"):
            smiles = smiles or session["actives"][0].get("smiles")
            cid = session["actives"][0].get("chembl_id")
        if not smiles:
            result = {
                "capability": "PRECONDITION",
                "capability_name": "Scientific prerequisite",
                "summary": "Retrosynthesis needs a structure.",
                "narrative": (
                    "No molecular structure is available for a route assessment. "
                    "A demonstration structure was not substituted."
                ),
                "tools_used": ["Session"],
                "provenance": {"kind": "precondition", "status": "not_run", "evidence": "not_run", "tool": None},
            }
        else:
            result = assess_synthesis(smiles, cid)
            result["narrative"] = (
                (result.get("narrative") or "")
                + " This is a rule-based complexity estimate, not a completed route from a retrosynthesis engine."
            )
            result["provenance"] = {
                "kind": "heuristic",
                "status": "derived",
                "evidence": "derived",
                "tool": "rule_based_mvp",
            }
            session_store.update_session(sid, routes=result.get("route"))
        result["trace"] = _trace(
            "Synthetic Feasibility",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [result.get("summary") or "Route assessment was not run"],
        )

    else:  # C8 export / explainability
        session = session_store.get_session(sid) or session
        result = {
            "capability": "C8",
            "capability_name": "Scientific Explainability / Capture",
            "summary": "Session snapshot ready for export — all prior cards remain addressable.",
            "narrative": (
                "Transparent session export with targets, actives, candidates, novelty, motifs, "
                "routes, and tool traces."
            ),
            "export": {
                "session_id": sid,
                "target": session.get("target"),
                "structures": session.get("structures"),
                "actives_count": len(session.get("actives") or []),
                "candidates_count": len(session.get("candidates") or []),
                "novelty_count": len(session.get("novelty") or []),
                "last_pdb_id": session.get("last_pdb_id"),
                "last_smiles": session.get("last_smiles"),
                "cards": session.get("cards") or [],
            },
            "tools_used": ["Orchestrator", "Session Store"],
            "parameters": {"session_id": sid},
            "trace": _trace(
                "Orchestrator",
                ["Session Store"],
                {"session_id": sid},
                [f"{len(session.get('cards') or [])} prior cards", "Export package assembled"],
            ),
        }

    # Drop bulky SVG from stored card payload (frontend re-fetches depict)
    def _strip_svg(obj):
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k == "svg" and isinstance(v, str) and len(v) > 200:
                    out[k] = None
                    out["svg_omitted"] = True
                else:
                    out[k] = _strip_svg(v)
            return out
        if isinstance(obj, list):
            return [_strip_svg(x) for x in obj]
        return obj

    if _drug_lookup_missed(query, result, session):
        answered = _answer_when_lookup_misses(query, session)
        if answered:
            result["narrative"] = answered
            result["spoken"] = answered
            result["llm_fallback"] = True
            result["provenance"] = {
                **(result.get("provenance") or {}),
                "evidence": "model",
                "status": "model",
                "tool": "OpenAI",
            }
            tools = list(result.get("tools_used") or [])
            if "LLM" not in tools:
                tools.append("LLM")
            result["tools_used"] = tools

    if not result.get("llm_fallback") and intent not in {"CX", "EXPLAIN", "PRECONDITION", "ROLE"}:
        spoken = _speak(query, result)
        if spoken:
            result["spoken"] = spoken
            tools = list(result.get("tools_used") or [])
            if "LLM" not in tools:
                tools.append("LLM")
            result["tools_used"] = tools

    classification = plan.get("classification") or {}
    requested = classification.get("capability") or intent
    triggered = [] if result.get("llm_fallback") else select_triggered_agents(query, requested, classification)
    for agent in triggered:
        agent["status"] = "answered"
    card = {
        "card_id": str(uuid.uuid4()),
        "query": query,
        "intent": intent,
        "intent_detail": result.get("intent_detail") or classification,
        "capability": result.get("capability"),
        "summary": result.get("summary"),
        "narrative": result.get("narrative"),
        "spoken": result.get("spoken"),
        "answer": (result.get("narrative") or "").strip(),
        "triggered_agents": triggered,
        "payload": _strip_svg({k: v for k, v in result.items() if k not in ("trace",)}),
        "trace": result.get("trace"),
        "visualization": _strip_svg(result.get("visualization")),
        "provenance": result.get("provenance"),
    }
    session = session_store.get_session(sid) or session
    orchestrator.remember(session, query=query, capability=intent, result=result)
    session_store.update_session(
        sid,
        research=session.get("research"),
        workflows=session.get("workflows"),
        candidates=session.get("candidates"),
        novelty=session.get("novelty"),
        docking_results=session.get("docking_results"),
        admet_results=session.get("admet_results"),
        selection=session.get("selection"),
    )
    session_store.append_card(sid, card)
    session = session_store.get_session(sid)

    summary = public_session(session)
    return {
        "session_id": sid,
        "intent": intent,
        "card": card,
        "session": summary,
    }


def export_session_markdown(session_id: str) -> str:
    session = session_store.get_session(session_id)
    if not session:
        return "# Session not found\n"
    lines = [
        "# Molecular Discovery Studio — Session Export",
        "",
        f"Session: `{session_id}`",
        "",
    ]
    t = session.get("target")
    if t:
        lines += [
            "## Target",
            f"- Gene: {t.get('gene_symbol')}",
            f"- UniProt: {t.get('uniprot_id')}",
            f"- Name: {t.get('name')}",
            "",
        ]
    if session.get("actives"):
        lines.append("## Known actives")
        for a in session["actives"][:20]:
            lines.append(
                f"- {a.get('chembl_id')} | pChEMBL={a.get('pchembl')} | `{a.get('smiles')}`"
            )
        lines.append("")
    if session.get("candidates"):
        lines.append("## Candidates")
        for c in session["candidates"][:20]:
            lines.append(
                f"- {c.get('candidate_id')} | QED={c.get('qed')} | `{c.get('smiles')}`"
            )
        lines.append("")
    lines.append("## Transcript")
    messages = session.get("messages") or []
    if not messages:
        lines.append("_No messages were stored._")
        lines.append("")
    for message in messages:
        speaker = "Scientist" if message.get("role") == "scientist" else "Studio"
        lines.append(f"### {speaker}")
        lines.append(message.get("content") or "")
        lines.append("")
    lines.append("## Traceable cards")
    for card in session.get("cards") or []:
        tr = card.get("trace") or {}
        lines.append(f"### {card.get('capability')} — {card.get('summary', '')[:120]}")
        lines.append(f"- Query: {card.get('query')}")
        answer = (card.get("answer") or card.get("narrative") or "").strip()
        lines.append("- Answer:")
        lines.append(answer or "(No answer was stored for this turn.)")
        lines.append(f"- Specialist: {tr.get('specialist')}")
        lines.append(f"- Tools: {', '.join(tr.get('tools') or []) or 'none'}")
        provenance = card.get("provenance") or (card.get("payload") or {}).get("provenance") or {}
        if provenance:
            lines.append(
                "- Provenance: "
                + ", ".join(f"{key}={value}" for key, value in provenance.items() if value is not None)
            )
        lines.append("")
    if session.get("workflows"):
        lines.append("## Workflows")
        for workflow in session["workflows"]:
            lines.append(
                f"- {workflow.get('kind')} {workflow.get('status')} `{workflow.get('workflow_id')}`"
            )
        lines.append("")
    return "\n".join(lines)


def export_session_json(session_id: str) -> dict | None:
    session = session_store.get_session(session_id)
    if not session:
        return None
    return export_session_package(session)


def depict(smiles: str) -> dict[str, Any]:
    return depict_smiles_svg(smiles)
