"""C1 — Target intelligence: gene → UniProt → PDB structures."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.services.chem.pdb_catalog import fetch_structure_catalog

logger = logging.getLogger(__name__)

# Curated demo fallbacks when APIs are unreachable
KNOWN_TARGETS: dict[str, dict[str, Any]] = {
    "JAK2": {
        "gene_symbol": "JAK2",
        "uniprot_id": "O60674",
        "name": "Tyrosine-protein kinase JAK2",
        "organism": "Homo sapiens",
        "function": "Non-receptor tyrosine kinase involved in cytokine signaling via JAK-STAT.",
        "pdb_ids": ["3UGC", "8BXH", "7LL4", "6VNE", "4D0W", "3KRR", "2B7A"],
    },
    "JAK1": {
        "gene_symbol": "JAK1",
        "uniprot_id": "P23458",
        "name": "Tyrosine-protein kinase JAK1",
        "organism": "Homo sapiens",
        "function": "Associates with cytokine receptors; key inflammatory signaling kinase.",
        "pdb_ids": ["6N7A", "4EHZ", "3EYG"],
    },
    "GLP1R": {
        "gene_symbol": "GLP1R",
        "uniprot_id": "P43220",
        "name": "Glucagon-like peptide 1 receptor",
        "organism": "Homo sapiens",
        "function": "GPCR for GLP-1; therapeutic target in metabolic disease / MASH.",
        "pdb_ids": ["6X1A", "5VAI", "7LCK"],
    },
}


# Spelled-out protein names scientists actually type, mapped to gene symbols.
PROTEIN_ALIASES: list[tuple[str, str]] = [
    (r"\bjanus\s+kinase[\s\-]*(\d)\b", "JAK{0}"),
    (r"\btyrosine[\s\-]protein\s+kinase\s+jak[\s\-]*(\d)\b", "JAK{0}"),
    (r"\bglucagon[\s\-]like\s+peptide[\s\-]*1\s+receptor\b", "GLP1R"),
    (r"\bglp[\s\-]?1\b", "GLP1R"),
]

# Uppercase words that look like gene symbols but aren't.
_NON_GENE_WORDS = {
    "WHAT", "WHICH", "WHO", "WHY", "HOW", "LIST", "SHOW", "TELL", "GIVE", "FIND",
    "THE", "AND", "FOR", "ARE", "ALL", "ANY", "CAN", "ITS", "THIS", "THAT", "FROM",
    "WITH", "NEW", "TOP", "AVAILABLE", "CRYSTAL", "STRUCTURE", "STRUCTURES",
    "PROTEIN", "DATA", "BANK", "PDB", "TARGET", "TARGETS", "DESIGN", "MOLECULE",
    "MOLECULES", "INHIBITOR", "INHIBITORS", "KINASE", "HUMAN", "ABOUT", "THERE",
    "THEIR", "THEM", "THESE", "THOSE", "EXPORT", "REPORT", "SESSION", "CHEMBL",
    "RDKIT", "SMILES", "NOVEL", "NOVELTY", "MOTIF", "MOTIFS", "SAR", "ADMET",
    "UNIPROT", "ALPHAFOLD", "COMPOUND", "COMPOUNDS", "LIGAND", "LIGANDS",
}


def _extract_gene(query: str) -> str | None:
    q = (query or "").strip()
    for pattern, template in PROTEIN_ALIASES:
        m = re.search(pattern, q, re.I)
        if m:
            return template.format(*m.groups()) if m.groups() else template
    m2 = re.search(r"\b(jak\d|egfr|braf|kras|alk|abl\d?|met|glp1r)\b", q, re.I)
    if m2:
        return m2.group(1).upper()
    # Gene symbols are conventionally written uppercase, so respect the original
    # casing instead of upper-casing the whole sentence (which matched "WHAT").
    for cand in re.findall(r"\b([A-Z][A-Z0-9]{2,9})\b", q):
        if cand.upper() not in _NON_GENE_WORDS:
            return cand.upper()
    return None


_NOT_A_PROTEIN = {
    "hello", "hi", "hey", "thanks", "thank", "you", "yes", "no", "ok", "okay",
    "please", "help", "next", "more", "again", "continue", "what", "why", "how",
    "who", "where", "when", "the", "a", "an", "of", "for", "and", "to", "me",
    "this", "that", "protein", "target", "new", "like", "study", "open", "about",
    "another", "want", "work", "start", "switch", "look", "tell", "capital",
    "weather", "joke", "france", "today",
}
_PROTEIN_CUE = re.compile(
    r"\b(protein|target|gene|study|switch|open|look at|work on|start with)\b",
    re.I,
)
_NOT_PROTEIN_TOPIC = re.compile(
    r"\b(capital|weather|joke|who are you|how are you|movie|song|president)\b",
    re.I,
)
_LEAD_IN = re.compile(
    r"^(?:please\s+)?(?:(?:let'?s|let us)\s+)?"
    r"(?:study|open|look at|switch to|work on|start with|"
    r"i want(?: to(?: study| open)?)?|"
    r"(?:a |the )?(?:new |another )?protein(?:\s+like)?|"
    r"(?:a |the )?target|"
    r"gene)\s+",
    re.I,
)


_DRUG_ASK = re.compile(
    r"\b(?:available|known|approved|marketed|clinical)\s+drugs?\b|"
    r"\bdrugs?\s+(?:for|against)\s+(?:this|the)\s+(?:target|protein)\b|"
    r"\bwhat\s+(?:are|drugs?)\b.+\bdrugs?\b|\bwhat\s+drugs?\b",
    re.I,
)


def asks_for_known_drugs(query: str) -> bool:
    """A request for drugs against the open target, not a new protein name."""
    return bool(_DRUG_ASK.search(query or ""))


def protein_mention(query: str) -> str | None:
    """The protein a scientist named, as a gene symbol or a protein name.

    This is not limited to a curated list. UniProt decides whether it is real.
    """
    text = (query or "").strip().strip("?.!")
    if not text or _NOT_PROTEIN_TOPIC.search(text):
        return None
    naming = bool(_PROTEIN_CUE.search(text))
    known = _extract_gene(text)
    if asks_for_known_drugs(text):
        return known
    if known and (naming or len(text.split()) <= 6):
        return known
    if len(text.split()) > 8 and not naming:
        return None
    peeled = _LEAD_IN.sub("", text).strip()
    peeled = re.sub(
        r"^(?:what(?:'s| is)|tell me about|about)\s+(?:the\s+)?",
        "",
        peeled,
        flags=re.I,
    ).strip()
    words = [
        word
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-]{0,40}", peeled)
        if word.lower() not in _NOT_A_PROTEIN
    ]
    if not words or len(words) > 5:
        return None
    if len(text.split()) > 6 and not naming:
        return None
    return " ".join(words)


def extract_gene_symbol(query: str) -> str | None:
    """A protein the scientist actually named. Never a default."""
    return protein_mention(query)


def _entry_labels(entry: dict) -> set[str]:
    labels: set[str] = set()
    for gene in entry.get("genes") or []:
        value = (gene.get("geneName") or {}).get("value")
        if value:
            labels.add(value)
        for synonym in gene.get("synonyms") or []:
            if synonym.get("value"):
                labels.add(synonym["value"])
    name = (
        (entry.get("proteinDescription") or {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value")
    )
    if name:
        labels.add(name)
    short = (entry.get("proteinDescription") or {}).get("recommendedName", {}).get("shortNames") or []
    for item in short:
        if item.get("value"):
            labels.add(item["value"])
    return labels


def _label_matches(labels: set[str], raw: str) -> bool:
    key = re.sub(r"[\s\-]", "", raw).lower()
    if not key:
        return False
    for label in labels:
        compact = re.sub(r"[\s\-]", "", label).lower()
        if compact == key:
            return True
        if len(key) >= 4 and raw.lower() in label.lower():
            return True
    return False


def _profile_from_entry(entry: dict, fallback_symbol: str) -> dict[str, Any]:
    genes = entry.get("genes") or []
    symbol = ""
    if genes:
        symbol = (genes[0].get("geneName") or {}).get("value") or ""
    return {
        "gene_symbol": (symbol or fallback_symbol).upper(),
        "uniprot_id": entry.get("primaryAccession"),
        "name": (
            (entry.get("proteinDescription") or {}).get("recommendedName", {}).get("fullName", {}).get("value")
            or entry.get("uniProtkbId")
            or symbol
            or fallback_symbol
        ),
        "organism": "Homo sapiens",
        "function": _first_function(entry),
        "source": "uniprot",
    }


def _uniprot_search(query: str) -> dict | None:
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {"query": query, "format": "json", "size": 5}
    with httpx.Client(timeout=12.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def resolve_uniprot(name: str) -> dict[str, Any] | None:
    """Match a gene symbol or a protein name to one reviewed human UniProt entry."""
    raw = (name or "").strip()
    if not raw:
        return None
    compact = re.sub(r"[\s\-]", "", raw)
    gene_u = compact.upper()
    if gene_u in ("GLP1", "GLP1R"):
        gene_u = "GLP1R"
    quoted = raw.replace('"', "").replace("\\", "")
    queries = []
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,14}", compact):
        queries.append(f"(gene_exact:{gene_u}) AND organism_id:9606 AND reviewed:true")
        queries.append(f"(gene:{gene_u}) AND organism_id:9606 AND reviewed:true")
    queries.append(f'(protein_name:"{quoted}") AND organism_id:9606 AND reviewed:true')
    queries.append(f"({quoted}) AND organism_id:9606 AND reviewed:true")
    try:
        for query in queries:
            payload = _uniprot_search(query) or {}
            for entry in payload.get("results") or []:
                if _label_matches(_entry_labels(entry), raw) or _label_matches(_entry_labels(entry), gene_u):
                    return _profile_from_entry(entry, gene_u)
    except Exception as exc:
        logger.warning("UniProt lookup failed for %s: %s", raw, exc)
        return None
    return None


def _first_function(entry: dict) -> str:
    for comment in entry.get("comments") or []:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts") or []
            if texts:
                return texts[0].get("value", "")[:1500]
    return ""


def fetch_pdb_ids(uniprot_id: str, limit: int = 8) -> list[str]:
    catalog = fetch_structure_catalog(uniprot_id, limit=limit)
    return [s["pdb_id"] for s in catalog.get("structures") or []]


def biological_role(query: str, session: dict[str, Any] | None = None) -> dict[str, Any]:
    """UniProt function comment for the named protein, or the protein already open."""
    gene = _extract_gene(query or "")
    stored = (session or {}).get("target") or {}
    profile = None
    if gene:
        profile = resolve_uniprot(gene)
    if not profile and stored.get("function"):
        profile = stored
    if not profile or not (profile.get("function") or "").strip():
        named = gene or stored.get("gene_symbol") or "this protein"
        return {
            "capability": "ROLE",
            "capability_name": "Pathway Insight",
            "summary": f"UniProt has no function comment stored here for {named}.",
            "narrative": (
                f"I looked for a UniProt function comment for {named}. "
                "None was available, so I am not going to describe the pathway from memory."
            ),
            "target": profile,
            "tools_used": ["UniProt"],
            "parameters": {"query": query, "gene": gene},
            "provenance": {"kind": "lookup", "status": "not_found", "evidence": "not_run", "tool": "UniProt"},
        }
    name = profile.get("name") or profile.get("gene_symbol")
    accession = profile.get("uniprot_id") or "n/a"
    symbol = profile.get("gene_symbol") or gene or "this protein"
    function = str(profile.get("function")).strip()
    narrative = (
        f"UniProt records this function for {name} ({symbol}, {accession}): {function} "
        "That text is the database comment. It is not a new literature review, "
        "and any citation inside it belongs to that comment."
    )
    return {
        "capability": "ROLE",
        "capability_name": "Pathway Insight",
        "summary": f"UniProt function comment for {symbol}.",
        "narrative": narrative,
        "target": profile,
        "tools_used": ["UniProt"],
        "parameters": {"query": query, "gene": symbol},
        "provenance": {
            "kind": "lookup",
            "status": "completed",
            "evidence": "measured",
            "tool": "UniProt",
            "source": "uniprot",
            "record_id": profile.get("uniprot_id"),
        },
    }


def build_target_profile(query: str) -> dict[str, Any]:
    """C1: resolve a named target to UniProt + filtered PDB catalog + profile."""
    mentioned = protein_mention(query)
    if not mentioned:
        return {
            "capability": "CONTEXT",
            "capability_name": "Set the context",
            "summary": "Tell me which protein you want to study.",
            "narrative": (
                "Name a protein, such as EGFR or the GLP-1 receptor, or a PDB code. "
                "Nothing was looked up yet."
            ),
            "target": None,
            "structures": [],
            "structure_count": 0,
            "needs_context": True,
            "tools_used": [],
            "parameters": {"query": query},
        }
    compact = re.sub(r"[\s\-]", "", mentioned).upper()
    if compact in {"GLP", "GLP1", "GLP1R"}:
        compact = "GLP1R"
    fallback = KNOWN_TARGETS.get(compact) if re.fullmatch(r"[A-Z0-9]{2,15}", compact) else None
    live = resolve_uniprot(mentioned)
    if not live and not fallback:
        return {
            "capability": "C1",
            "capability_name": "Target Intelligence",
            "summary": f"No reviewed human protein matched {mentioned}.",
            "narrative": (
                f"I looked up “{mentioned}” in UniProt as a gene symbol and as a protein name. "
                "No reviewed human protein matched, so this session was not switched to it. "
                "Use a gene symbol such as TP53, or a protein name such as insulin."
            ),
            "target": None,
            "structures": [],
            "structure_count": 0,
            "tools_used": ["UniProt"],
            "parameters": {"query": query, "mentioned": mentioned},
            "provenance": {"kind": "lookup", "status": "not_found", "evidence": "not_run", "tool": "UniProt", "source": "uniprot"},
        }
    chosen = live or fallback or {}
    profile = {
        "gene_symbol": chosen.get("gene_symbol") or compact,
        "uniprot_id": chosen.get("uniprot_id"),
        "name": chosen.get("name") or mentioned,
        "organism": chosen.get("organism") or "Homo sapiens",
        "function": chosen.get("function") or "",
        "source": chosen.get("source") or ("curated" if fallback else "partial"),
    }
    gene_u = profile["gene_symbol"]

    catalog: dict[str, Any] = {"structures": [], "total_count": 0, "filters": {}, "source": "none"}
    if profile.get("uniprot_id"):
        catalog = fetch_structure_catalog(profile["uniprot_id"], limit=10)
    if not catalog.get("structures") and fallback:
        catalog = fetch_structure_catalog(fallback["uniprot_id"], limit=10)

    structures = catalog.get("structures") or []
    total = catalog.get("total_count") or len(structures)
    filters = catalog.get("filters") or {}
    max_res = filters.get("max_resolution_A", 2.5)

    summary = (
        f"RCSB lists {total} entries for {profile['name']} "
        f"({profile['gene_symbol']}, UniProt {profile.get('uniprot_id') or 'n/a'})"
    )
    if max_res:
        summary += f" at {max_res} Å or better"
    if filters.get("nonpolymer_required") or filters.get("require_co_crystal_ligand"):
        summary += (
            " that contain a non-polymer component. Nucleotides such as GDP and ions "
            "such as magnesium are included in that count"
        )
    summary += "."
    if filters.get("ligand_filter") == "other_component":
        inspected = filters.get("inspected") or len(structures)
        summary += (
            f" The {len(structures)} rows below are the highest-resolution entries among "
            f"{inspected} inspected that also contain a bound component other than a nucleotide, "
            "ion, or common buffer."
        )
    elif structures:
        summary += f" The {len(structures)} highest-resolution entries are listed."

    return {
        "capability": "C1",
        "capability_name": "Target Intelligence",
        "summary": summary,
        "target": profile,
        "structures": structures,
        "structure_count": total,
        "structure_filters": filters,
        "default_pdb_id": structures[0]["pdb_id"] if structures else None,
        "narrative": summary,
        "tools_used": ["UniProt", "RCSB PDB", "Mol*"],
        "parameters": {"query": query, "gene": gene_u, "filters": filters},
    }
