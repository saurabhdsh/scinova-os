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
    for cand in re.findall(r"\b([A-Z][A-Z0-9]{1,9})\b", q):
        if cand.upper() not in _NON_GENE_WORDS:
            return cand.upper()
    return None


def resolve_uniprot(gene: str) -> dict[str, Any] | None:
    gene_u = gene.upper().replace("-", "")
    if gene_u in ("GLP1", "GLP-1R"):
        gene_u = "GLP1R"
    try:
        url = "https://rest.uniprot.org/uniprotkb/search"
        params = {
            "query": f"gene:{gene_u} AND organism_id:9606 AND reviewed:true",
            "format": "json",
            "size": 1,
        }
        with httpx.Client(timeout=12.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            results = r.json().get("results") or []
            if not results:
                return None
            entry = results[0]
            return {
                "gene_symbol": gene_u,
                "uniprot_id": entry.get("primaryAccession"),
                "name": (entry.get("proteinDescription") or {}).get("recommendedName", {}).get("fullName", {}).get("value")
                or entry.get("uniProtkbId"),
                "organism": "Homo sapiens",
                "function": _first_function(entry),
                "source": "uniprot",
            }
    except Exception as exc:
        logger.warning("UniProt lookup failed for %s: %s", gene_u, exc)
        return None


def _first_function(entry: dict) -> str:
    for comment in entry.get("comments") or []:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts") or []
            if texts:
                return texts[0].get("value", "")[:400]
    return ""


def fetch_pdb_ids(uniprot_id: str, limit: int = 8) -> list[str]:
    catalog = fetch_structure_catalog(uniprot_id, limit=limit)
    return [s["pdb_id"] for s in catalog.get("structures") or []]


def build_target_profile(query: str) -> dict[str, Any]:
    """C1: resolve target name to UniProt + filtered PDB catalog + profile."""
    gene = _extract_gene(query) or "JAK2"
    gene_u = gene.upper()
    if gene_u.startswith("GLP"):
        gene_u = "GLP1R"

    fallback = KNOWN_TARGETS.get(gene_u)
    live = resolve_uniprot(gene_u)
    profile = {
        "gene_symbol": gene_u,
        "uniprot_id": (live or fallback or {}).get("uniprot_id"),
        "name": (live or fallback or {}).get("name") or gene_u,
        "organism": (live or fallback or {}).get("organism") or "Homo sapiens",
        "function": (live or fallback or {}).get("function") or "",
        "source": (live or {}).get("source") or ("curated" if fallback else "partial"),
    }

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
        f"There are currently {total} crystal structures of {profile['name']} "
        f"({profile['gene_symbol']}, UniProt {profile.get('uniprot_id') or 'n/a'}) "
        f"in the PDB"
    )
    if filters.get("require_co_crystal_ligand") and max_res:
        summary += (
            f" that feature a co-crystal ligand and possess a resolution of "
            f"{max_res} Å or better"
        )
    summary += f". A representative selection of {len(structures)} structure(s) is listed below."
    if profile.get("function"):
        summary += f" {profile['function'][:140]}"

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
