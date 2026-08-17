"""C6 — Structure assets: depict 2D SMILES, Mol* URLs, optional SDF."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def molstar_viewer_url(pdb_id: str | None = None, structure_url: str | None = None) -> str:
    if pdb_id:
        return f"https://molstar.org/viewer/?pdb={pdb_id.upper()}"
    if structure_url:
        from urllib.parse import quote
        return f"https://molstar.org/viewer/#structure={quote(structure_url, safe='')}"
    return "https://molstar.org/viewer/"


def rcsb_mmcif_url(pdb_id: str) -> str:
    return f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"


def depict_smiles_svg(smiles: str, width: int = 280, height: int = 200) -> dict[str, Any]:
    """Render 2D SVG from SMILES via RDKit; fallback placeholder SVG."""
    smiles = (smiles or "").strip()
    if not smiles:
        return {"ok": False, "error": "Empty SMILES"}

    try:
        from rdkit import Chem
        from rdkit.Chem import Draw

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"ok": False, "error": "Invalid SMILES", "smiles": smiles}
        drawer = Draw.MolDraw2DSVG(width, height)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()
        return {
            "ok": True,
            "smiles": smiles,
            "format": "svg",
            "svg": svg,
            "engine": "rdkit",
            "width": width,
            "height": height,
        }
    except Exception as exc:
        logger.info("RDKit depict unavailable (%s) — placeholder", exc)
        # Minimal placeholder SVG
        safe = smiles[:40].replace("<", "").replace(">", "")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<rect width="100%" height="100%" fill="#f8fafc"/>'
            f'<text x="50%" y="45%" text-anchor="middle" fill="#64748b" font-size="12">2D depiction</text>'
            f'<text x="50%" y="60%" text-anchor="middle" fill="#94a3b8" font-size="10">{safe}</text>'
            f"</svg>"
        )
        return {
            "ok": True,
            "smiles": smiles,
            "format": "svg",
            "svg": svg,
            "engine": "placeholder",
            "width": width,
            "height": height,
            "note": "Install RDKit for publication-quality 2D",
        }


def build_visualization_payload(
    *,
    pdb_id: str | None = None,
    smiles: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    if pdb_id:
        assets.append({
            "asset_id": f"pdb-{pdb_id}",
            "type": "3d",
            "label": label or pdb_id,
            "pdb_id": pdb_id.upper(),
            "file_url": rcsb_mmcif_url(pdb_id),
            "viewer_url": molstar_viewer_url(pdb_id=pdb_id),
            "representations": ["cartoon", "surface", "stick", "ball-and-stick"],
        })
    depict = None
    if smiles:
        depict = depict_smiles_svg(smiles)
        assets.append({
            "asset_id": f"smi-{hash(smiles) & 0xFFFF:x}",
            "type": "2d",
            "label": label or "ligand",
            "smiles": smiles,
            "depict": depict,
        })
        # Ligand-only Mol* via pubchem 3D when possible is complex; show SMILES in session
    return {
        "capability": "C6",
        "capability_name": "Molecular Visualization",
        "summary": (
            f"Interactive 3D via Mol*"
            + (f" for {pdb_id}" if pdb_id else "")
            + (f"; 2D depiction for ligand" if smiles else "")
        ),
        "narrative": "2D depiction and interactive Mol* 3D molecular graph.",
        "assets": assets,
        "pdb_id": pdb_id.upper() if pdb_id else None,
        "smiles": smiles,
        "file_url": rcsb_mmcif_url(pdb_id) if pdb_id else None,
        "viewer_url": molstar_viewer_url(pdb_id=pdb_id) if pdb_id else None,
        "tools_used": ["Mol*", "RDKit"] if smiles else ["Mol*"],
        "parameters": {"pdb_id": pdb_id, "smiles": smiles},
        "controls": ["rotate", "zoom", "pan", "reset", "fullscreen"],
    }
