"""Build / load the expanded drug-like SMILES corpus (ChEMBL + curated seeds)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import httpx

from app.services.chem.smiles_corpus import TRAINING_SMILES

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
CORPUS_PATH = DATA_DIR / "druglike_smiles.txt"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"


def _valid_druglike(smiles: str) -> str | None:
    smi = (smiles or "").strip()
    if not smi or "." in smi:
        return None
    if len(smi) < 8 or len(smi) > 180:
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Lipinski

        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return None
        Chem.SanitizeMol(mol)
        heavy = mol.GetNumHeavyAtoms()
        if heavy < 10 or heavy > 55:
            return None
        mw = Descriptors.MolWt(mol)
        if mw < 150 or mw > 650:
            return None
        if Lipinski.NumHDonors(mol) > 7 or Lipinski.NumHAcceptors(mol) > 12:
            return None
        return Chem.MolToSmiles(mol)
    except Exception:
        return None


def _canonicalize_loose(smiles: str) -> str | None:
    """Accept curated seeds even when slightly outside drug-like gates."""
    smi = (smiles or "").strip()
    if not smi:
        return None
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return smi
        return Chem.MolToSmiles(mol)
    except Exception:
        return smi


def _fetch_page(client: httpx.Client, params: dict) -> list[dict]:
    r = client.get(
        f"{CHEMBL}/molecule.json",
        params=params,
        headers={"Accept": "application/json"},
    )
    r.raise_for_status()
    data = r.json()
    return data.get("molecules") or []


def fetch_chembl_smiles(target: int, *, page_size: int = 100) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    queries = [
        {"max_phase": 4, "molecule_type": "Small molecule"},
        {"max_phase": 3, "molecule_type": "Small molecule"},
        {"max_phase": 2, "molecule_type": "Small molecule"},
        {"molecule_type": "Small molecule"},
    ]
    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        for q in queries:
            offset = 0
            while len(out) < target:
                params = {**q, "limit": page_size, "offset": offset, "format": "json"}
                try:
                    rows = _fetch_page(client, params)
                except Exception as exc:
                    logger.warning("ChEMBL page failed (%s): %s", q, exc)
                    break
                if not rows:
                    break
                for mol in rows:
                    structs = mol.get("molecule_structures") or {}
                    smi = structs.get("canonical_smiles")
                    if not smi:
                        continue
                    canon = _valid_druglike(smi)
                    if not canon or canon in seen:
                        continue
                    seen.add(canon)
                    out.append(canon)
                    if len(out) >= target:
                        break
                offset += page_size
                logger.info("Fetched %s / %s (query=%s offset=%s)", len(out), target, q, offset)
                if len(rows) < page_size:
                    break
            if len(out) >= target:
                break
    return out


def _pad_with_variants(smiles: list[str], *, target: int) -> list[str]:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    out = list(smiles)
    seen = set(out)
    rxns = [
        AllChem.ReactionFromSmarts("[cH:1]>>[c:1]C"),
        AllChem.ReactionFromSmarts("[cH:1]>>[c:1]F"),
        AllChem.ReactionFromSmarts("[cH:1]>>[c:1]Cl"),
    ]
    i = 0
    while len(out) < target and i < max(len(smiles), 1) * 30:
        base = smiles[i % len(smiles)]
        i += 1
        mol = Chem.MolFromSmiles(base)
        if mol is None:
            continue
        for rxn in rxns:
            try:
                for prod_tuple in rxn.RunReactants((mol,))[:2]:
                    p = prod_tuple[0]
                    Chem.SanitizeMol(p)
                    smi = Chem.MolToSmiles(p)
                    if smi and smi not in seen:
                        seen.add(smi)
                        out.append(smi)
                        if len(out) >= target:
                            return out
            except Exception:
                continue
    return out


def build_expanded_corpus(target: int = 4000) -> Path:
    """Fetch/filter ChEMBL SMILES and write druglike_smiles.txt (3K–5K)."""
    target = max(3000, min(5000, int(target)))
    seen: set[str] = set()
    seeds: list[str] = []

    for s in TRAINING_SMILES:
        canon = _canonicalize_loose(s)
        if canon and canon not in seen:
            seen.add(canon)
            seeds.append(canon)

    logger.info("Starting from %s curated seeds; fetching to %s…", len(seeds), target)
    for s in fetch_chembl_smiles(target):
        if s not in seen:
            seen.add(s)
            seeds.append(s)
        if len(seeds) >= target:
            break

    if len(seeds) < 3000:
        logger.warning("Only %s unique SMILES — padding with RDKit Me/F/Cl variants", len(seeds))
        seeds = _pad_with_variants(seeds, target=3000)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    final = seeds[:5000]
    CORPUS_PATH.write_text("\n".join(final) + "\n", encoding="utf-8")
    logger.info("Wrote %s SMILES → %s", len(final), CORPUS_PATH)
    return CORPUS_PATH


def load_expanded_smiles() -> list[str]:
    if not CORPUS_PATH.is_file():
        return []
    return [ln.strip() for ln in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
