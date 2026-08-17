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
from app.services.chem.target_intel import build_target_profile
from app.services.chem.structure_dossier import build_structure_dossier, extract_pdb_id
from app.services.chem.pocket_analysis import analyze_pockets


INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("C1", [r"tell me about", r"target profile", r"what is", r"uniprot", r"structures for", r"about\s+[A-Z0-9]"]),
    ("C2", [r"known.*(inhibitor|active|ligand)", r"chembl", r"show.*inhibitor", r"bioactive", r"potent.*compound"]),
    ("C3", [r"design", r"generat.*candid", r"de novo", r"new molecule", r"scaffold"]),
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
    # Design against a pocket must win over bare "pocket" analysis
    if re.search(r"design|generat.*candid|de novo|new molecule|scaffold|small molecules? against", q):
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
    if re.search(r"known.*(inhibitor|active|ligand)|chembl|show.*inhibitor|bioactive", q):
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
        return "C1"
    return max(scores.items(), key=lambda x: x[1])[0]


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
) -> dict[str, Any]:
    session = session_store.ensure_session(session_id, user_id)
    sid = session["id"]
    intent = intent_override or classify_intent(query)

    # Ensure we have target context for downstream steps
    if intent != "C1" and not session.get("target"):
        # Soft-bootstrap C1 from query if gene mentioned
        boot = build_target_profile(query)
        session_store.update_session(
            sid,
            target=boot["target"],
            structures=boot["structures"],
            last_pdb_id=boot.get("default_pdb_id"),
        )
        session = session_store.get_session(sid) or session

    result: dict[str, Any]

    if intent == "C1":
        result = build_target_profile(query)
        session_store.update_session(
            sid,
            target=result["target"],
            structures=result["structures"],
            last_pdb_id=result.get("default_pdb_id"),
        )
        # Attach Mol* viz for default structure
        if result.get("default_pdb_id"):
            viz = build_visualization_payload(pdb_id=result["default_pdb_id"])
            result["visualization"] = viz
        result["trace"] = _trace(
            "Target Intelligence",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"Resolved {result['target'].get('gene_symbol')} → {result['target'].get('uniprot_id')}",
                f"{result.get('structure_count') or len(result.get('structures') or [])} PDB structures "
                f"(showing {len(result.get('structures') or [])})",
            ],
        )

    elif intent == "C2":
        target = session.get("target") or {}
        result = discover_known_actives(target.get("uniprot_id"), target.get("gene_symbol"))
        session_store.update_session(sid, actives=result["actives"])
        if result["actives"]:
            top = result["actives"][0]
            result["visualization"] = build_visualization_payload(
                smiles=top.get("smiles"),
                pdb_id=session.get("last_pdb_id"),
                label=top.get("pref_name") or top.get("chembl_id"),
            )
            session_store.update_session(sid, last_smiles=top.get("smiles"))
        result["trace"] = _trace(
            "Known Bioactive Discovery",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [f"{len(result['actives'])} actives from {result.get('source')}"],
        )

    elif intent == "C3":
        target = session.get("target") or {}
        refs = [a.get("smiles") for a in (session.get("actives") or [])[:5] if a.get("smiles")]
        pdb_id = extract_pdb_id(query) or session.get("last_pdb_id")
        receptor_based = bool(
            pdb_id
            or re.search(r"against|receptor|pocket|rbdd|cvae|dock", query, re.I)
        )
        # Parse "design N ..." if present
        m_n = re.search(r"\b(\d+)\s+(?:small\s+)?molecules?\b", query, re.I)
        max_n = int(m_n.group(1)) if m_n else 12
        max_n = max(1, min(max_n, 20))
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
        session_store.update_session(sid, candidates=result["candidates"])
        if pdb_id:
            session_store.update_session(sid, last_pdb_id=pdb_id)
        if result["candidates"]:
            c0 = result["candidates"][0]
            result["visualization"] = build_visualization_payload(
                smiles=c0["smiles"],
                pdb_id=pdb_id or session.get("last_pdb_id"),
                label=c0["candidate_id"],
            )
            session_store.update_session(sid, last_smiles=c0["smiles"])
        result["trace"] = _trace(
            "Molecule Design",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [
                f"{len(result['candidates'])} candidates generated",
                *( [f"Receptor-based vs {pdb_id} / {pocket_id}"] if receptor_based else [] ),
            ],
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
        cands = session.get("candidates") or []
        acts = session.get("actives") or []
        if not cands:
            # generate then assess
            target = session.get("target") or {}
            designed = design_candidates(target.get("gene_symbol"))
            cands = designed["candidates"]
            session_store.update_session(sid, candidates=cands)
        if not acts:
            target = session.get("target") or {}
            acts = discover_known_actives(target.get("uniprot_id"), target.get("gene_symbol"))["actives"]
            session_store.update_session(sid, actives=acts)
        result = assess_novelty(cands, acts)
        session_store.update_session(sid, novelty=result["novelty"])
        result["trace"] = _trace(
            "Novelty Assessment",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [f"Compared {len(cands)} candidates to {len(acts)} references"],
        )

    elif intent == "C5":
        cands = session.get("candidates") or session.get("actives") or []
        if not cands:
            target = session.get("target") or {}
            cands = design_candidates(target.get("gene_symbol"))["candidates"]
            session_store.update_session(sid, candidates=cands)
        target = session.get("target") or {}
        result = reason_motifs(target.get("gene_symbol"), cands)
        session_store.update_session(sid, motifs=result)
        result["trace"] = _trace(
            "Med-Chem Reasoning",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [f"Motif matrix for {len(result.get('motif_matrix') or [])} molecules"],
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
            smiles = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"
            cid = "demo"
        result = assess_synthesis(smiles, cid)
        session_store.update_session(sid, routes=result.get("route"))
        result["trace"] = _trace(
            "Synthetic Feasibility",
            result.get("tools_used") or [],
            result.get("parameters") or {},
            [f"Status={result['route']['status']}", f"Steps≈{result['route']['steps_estimate']}"],
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

    card = {
        "card_id": str(uuid.uuid4()),
        "query": query,
        "intent": intent,
        "capability": result.get("capability"),
        "summary": result.get("summary"),
        "narrative": result.get("narrative"),
        "payload": _strip_svg({k: v for k, v in result.items() if k not in ("trace",)}),
        "trace": result.get("trace"),
        "visualization": _strip_svg(result.get("visualization")),
    }
    session_store.append_card(sid, card)
    session = session_store.get_session(sid)

    return {
        "session_id": sid,
        "intent": intent,
        "card": card,
        "session": {
            "id": sid,
            "target": session.get("target") if session else None,
            "last_pdb_id": session.get("last_pdb_id") if session else None,
            "last_smiles": session.get("last_smiles") if session else None,
            "structures_count": len((session or {}).get("structures") or []),
            "actives_count": len((session or {}).get("actives") or []),
            "candidates_count": len((session or {}).get("candidates") or []),
            "cards_count": len((session or {}).get("cards") or []),
        },
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
    lines.append("## Traceable cards")
    for card in session.get("cards") or []:
        tr = card.get("trace") or {}
        lines.append(f"### {card.get('capability')} — {card.get('summary', '')[:120]}")
        lines.append(f"- Query: {card.get('query')}")
        lines.append(f"- Specialist: {tr.get('specialist')}")
        lines.append(f"- Tools: {', '.join(tr.get('tools') or [])}")
        lines.append("")
    return "\n".join(lines)


def depict(smiles: str) -> dict[str, Any]:
    return depict_smiles_svg(smiles)
