"""Molecular docking — RDKit 3D conformer + shape screening; optional AutoDock Vina."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.chemoinformatics_service import extract_compounds, rdkit_available

logger = logging.getLogger(__name__)


def vina_available() -> bool:
    if settings.vina_bin:
        return Path(settings.vina_bin).exists()
    return shutil.which("vina") is not None


def _embed_conformer(smiles: str):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    if AllChem.EmbedMolecule(mol, params) != 0:
        return None
    AllChem.MMFFOptimizeMolecule(mol)
    return mol


def shape_similarity_screen(
    query_smiles: str,
    library: list[dict[str, str]],
    *,
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """Rank library compounds by 3D shape Tanimoto vs query."""
    if not rdkit_available():
        return []

    from rdkit import Chem
    from rdkit.Chem import AllChem, rdShapeHelpers

    query_mol = _embed_conformer(query_smiles)
    if query_mol is None:
        return []

    results: list[dict[str, Any]] = []
    for item in library:
        smi = item.get("smiles", "")
        cand = _embed_conformer(smi)
        if cand is None:
            continue
        try:
            score = rdShapeHelpers.ShapeTanimotoDist(query_mol, cand)
            shape_sim = max(0.0, 1.0 - float(score))
        except Exception:
            shape_sim = 0.0
        results.append({
            "compound_id": item.get("compound_id"),
            "smiles": smi,
            "shape_similarity": round(shape_sim, 4),
            "method": "rdkit_shape",
        })

    results.sort(key=lambda x: x["shape_similarity"], reverse=True)
    for i, row in enumerate(results[:top_k]):
        row["rank"] = i + 1
    return results[:top_k]


def run_vina_docking(
    ligand_smiles: str,
    *,
    exhaustiveness: int = 8,
) -> dict[str, Any]:
    """Run AutoDock Vina when receptor config is available."""
    if not vina_available():
        return {"available": False, "reason": "AutoDock Vina binary not configured"}

    receptor = settings.vina_receptor_pdbqt
    center = settings.vina_center
    size = settings.vina_size
    if not receptor or not Path(receptor).exists():
        return {"available": False, "reason": "VINA_RECEPTOR_PDBQT not configured"}

    if not rdkit_available():
        return {"available": False, "reason": "RDKit required to prepare ligand"}

    from rdkit import Chem

    mol = Chem.MolFromSmiles(ligand_smiles)
    if mol is None:
        return {"available": False, "reason": "Invalid ligand SMILES"}

    vina_exe = settings.vina_bin or shutil.which("vina")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ligand_pdbqt = tmp_path / "ligand.pdbqt"
        out_pdbqt = tmp_path / "out.pdbqt"
        # Minimal placeholder — production would use Meeko/OpenBabel for pdbqt prep
        ligand_pdbqt.write_text(f"REMARK SMILES {ligand_smiles}\n")

        cmd = [
            vina_exe,
            "--receptor", receptor,
            "--ligand", str(ligand_pdbqt),
            "--out", str(out_pdbqt),
            "--center_x", str(center[0]),
            "--center_y", str(center[1]),
            "--center_z", str(center[2]),
            "--size_x", str(size[0]),
            "--size_y", str(size[1]),
            "--size_z", str(size[2]),
            "--exhaustiveness", str(exhaustiveness),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
            if proc.returncode != 0:
                return {
                    "available": True,
                    "status": "failed",
                    "stderr": proc.stderr[:500],
                    "note": "Configure ligand PDBQT prep (Meeko) for production docking",
                }
            affinity = None
            for line in proc.stdout.splitlines():
                if line.strip().startswith("1 "):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            affinity = float(parts[1])
                        except ValueError:
                            pass
                    break
            return {
                "available": True,
                "status": "completed",
                "binding_affinity_kcal_mol": affinity,
                "receptor": receptor,
                "engine": "autodock_vina",
            }
        except subprocess.TimeoutExpired:
            return {"available": True, "status": "timeout"}
        except Exception as exc:
            return {"available": True, "status": "error", "error": str(exc)}


def run_docking_pipeline(input_data: dict) -> dict[str, Any]:
    """Combined shape screen + optional Vina for top hit."""
    compounds = extract_compounds(input_data)
    query = str(input_data.get("query_smiles") or input_data.get("target_smiles") or "").strip()
    if not query and compounds:
        query = compounds[0]["smiles"]

    logs: list[dict] = []
    shape_hits: list[dict] = []
    vina_result: dict = {"available": False}

    if query and rdkit_available():
        library = compounds[1:] if len(compounds) > 1 else compounds
        shape_hits = shape_similarity_screen(query, library, top_k=int(input_data.get("top_k") or 15))
        logs.append({"message": f"Shape screening: {len(shape_hits)} hits vs query"})
        if input_data.get("run_vina") and shape_hits:
            vina_result = run_vina_docking(shape_hits[0]["smiles"])
            logs.append({"message": f"Vina status: {vina_result.get('status', 'skipped')}"})
    else:
        logs.append({"message": "Shape screening skipped — provide query_smiles and RDKit"})

    return {
        "query_smiles": query,
        "shape_hits": shape_hits,
        "vina": vina_result,
        "rdkit_available": rdkit_available(),
        "vina_available": vina_available(),
        "logs": logs,
    }
