"""External data source connectors — PubMed, KEGG, ELN/LIMS."""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
KEGG_BASE = "https://rest.kegg.jp"

ELN_SOURCE_TYPES = ("eln_export", "protocol", "study_report", "lab_notebook")


def _http_get(url: str, params: dict | None = None, timeout: float = 20.0) -> httpx.Response | None:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp
    except Exception as exc:
        logger.warning("HTTP request failed (%s): %s", url, exc)
        return None


def search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    """Search PubMed via NCBI E-utilities and return article summaries."""
    if not query.strip():
        return []

    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email

    search_resp = _http_get(PUBMED_ESEARCH, params)
    if not search_resp:
        return []

    try:
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []
    if not pmids:
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    if settings.ncbi_email:
        fetch_params["email"] = settings.ncbi_email

    fetch_resp = _http_get(PUBMED_EFETCH, fetch_params, timeout=30.0)
    if not fetch_resp:
        return []

    articles = []
    try:
        root = ET.fromstring(fetch_resp.text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            title_el = article.find(".//ArticleTitle")
            abstract_el = article.find(".//AbstractText")
            journal_el = article.find(".//Title")
            year_el = article.find(".//PubDate/Year")

            pmid = pmid_el.text if pmid_el is not None else ""
            title = "".join(title_el.itertext()) if title_el is not None else "Untitled"
            abstract = "".join(abstract_el.itertext()) if abstract_el is not None else ""
            journal = journal_el.text if journal_el is not None else ""
            year = year_el.text if year_el is not None else ""

            authors = []
            for author in article.findall(".//Author")[:4]:
                last = author.find("LastName")
                if last is not None and last.text:
                    authors.append(last.text)

            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract[:1200],
                "journal": journal,
                "year": year,
                "authors": authors,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            })
    except ET.ParseError as exc:
        logger.warning("PubMed XML parse failed: %s", exc)

    return articles


def _extract_gene_symbols(text: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", text.upper())
    blocklist = {"RA", "OR", "AND", "THE", "DNA", "RNA", "PDF", "DOI", "NCT", "FDA", "II", "III"}
    seen = []
    for t in tokens:
        if t in blocklist or t in seen:
            continue
        if len(t) >= 2:
            seen.append(t)
        if len(seen) >= 3:
            break
    return seen


def search_kegg(query: str, max_results: int = 5) -> list[dict]:
    """Search KEGG pathways and genes related to the query."""
    results = []
    symbols = _extract_gene_symbols(query)
    search_terms = symbols or [w for w in re.split(r"\W+", query) if len(w) > 3][:2]

    for term in search_terms[:2]:
        resp = _http_get(f"{KEGG_BASE}/find/genes/{term}", timeout=15.0)
        if not resp or not resp.text.strip():
            continue

        for line in resp.text.strip().split("\n")[:max_results]:
            if not line or line.startswith("---"):
                continue
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            kegg_id, description = parts[0], parts[1]

            pathway_resp = _http_get(f"{KEGG_BASE}/link/pathway/{kegg_id}", timeout=10.0)
            pathways = []
            if pathway_resp and pathway_resp.text.strip():
                for pline in pathway_resp.text.strip().split("\n")[:4]:
                    if "\t" in pline:
                        _, pathway_id = pline.split("\t", 1)
                        pathways.append(pathway_id.replace("path:", ""))

            results.append({
                "kegg_id": kegg_id,
                "description": description,
                "pathways": pathways,
                "search_term": term,
                "url": f"https://www.kegg.jp/entry/{kegg_id.split(':')[-1]}",
            })

    return results[:max_results]


def fetch_eln_records(db, query: str, limit: int = 5) -> list[dict]:
    """Pull experiment records from indexed ELN/protocol documents in the Data Fabric."""
    from app.models.db_models import Document, DocumentChunk

    q = (query or "").lower()
    docs = (
        db.query(Document)
        .filter(Document.status == "indexed")
        .filter(Document.source_type.in_(ELN_SOURCE_TYPES))
        .order_by(Document.updated_at.desc())
        .limit(20)
        .all()
    )
    if not docs:
        docs = (
            db.query(Document)
            .filter(Document.status == "indexed")
            .order_by(Document.updated_at.desc())
            .limit(10)
            .all()
        )

    records = []
    for doc in docs:
        if q and q not in doc.title.lower() and q not in (doc.source_type or "").lower():
            meta = doc.metadata_json or {}
            if q not in str(meta).lower():
                continue

        chunk = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
            .first()
        )
        excerpt = (chunk.content[:600] if chunk else "") or ""
        records.append({
            "record_id": doc.id,
            "title": doc.title,
            "source_type": doc.source_type,
            "captured_at": doc.updated_at.isoformat() if doc.updated_at else "",
            "excerpt": excerpt,
            "connector": "eln_lims",
        })
        if len(records) >= limit:
            break

    return records


def integration_status(db=None) -> dict:
    """Health check for external connectors."""
    pubmed_ok = False
    kegg_ok = False
    eln_count = 0

    test = _http_get(PUBMED_ESEARCH, {"db": "pubmed", "term": "aspirin", "retmax": 1, "retmode": "json"})
    pubmed_ok = test is not None

    kegg_test = _http_get(f"{KEGG_BASE}/find/genes/JAK1", timeout=10.0)
    kegg_ok = kegg_test is not None and bool(kegg_test.text.strip())

    if db is not None:
        from app.models.db_models import Document
        eln_count = db.query(Document).filter(
            Document.source_type.in_(ELN_SOURCE_TYPES),
            Document.status == "indexed",
        ).count()

    return {
        "pubmed": {"status": "connected" if pubmed_ok else "unavailable", "provider": "NCBI E-utilities"},
        "kegg": {"status": "connected" if kegg_ok else "unavailable", "provider": "KEGG REST API"},
        "eln_lims": {
            "status": "connected" if eln_count else "no_records",
            "provider": "SciFabric Data Fabric",
            "indexed_records": eln_count,
        },
        "checked_at": datetime.utcnow().isoformat(),
    }
