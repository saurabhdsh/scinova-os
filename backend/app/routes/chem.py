"""Molecular Discovery Studio API routes (C1–C8)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.db_models import User
from app.services.chem import session_store
from app.services.chem.intent_engine import classify_scientific_intent
from app.services.chem.orchestrator import depict, export_session_json, export_session_markdown, run_chem_query
from app.services.chem.value_chain_bridge import select_triggered_agents
from app.services.chem.structure_assets import molstar_viewer_url, rcsb_mmcif_url

router = APIRouter(prefix="/chem", tags=["molecular-discovery-studio"])


class ChemQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str | None = None
    intent: str | None = None
    selected_molecule_id: str | None = None


class SelectionRequest(BaseModel):
    molecule_id: str | None = None
    pdb_id: str | None = None


class ImportRequest(BaseModel):
    session: dict | None = None
    transcript: list | None = None
    cards: list | None = None


class DepictRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    width: int = 280
    height: int = 200


@router.post("/session")
def create_chem_session(user: User = Depends(get_current_user)):
    return session_store.create_session(user.id)


@router.get("/session/{session_id}")
def get_chem_session(session_id: str, user: User = Depends(get_current_user)):
    s = session_store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.post("/route")
def chem_route(body: ChemQueryRequest, user: User = Depends(get_current_user)):
    """Name the value-chain agent before the slower tool run starts."""
    _ = user
    session = session_store.get_session(body.session_id) if body.session_id else None
    classified = classify_scientific_intent(body.query, session)
    capability = classified.get("capability")
    return {
        "capability": capability,
        "agents": select_triggered_agents(body.query, capability, classified),
    }


@router.post("/query")
def chem_query(body: ChemQueryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = db  # reserved for future persistence
    return run_chem_query(
        body.query,
        session_id=body.session_id,
        user_id=user.id,
        intent_override=body.intent,
        selected_molecule_id=body.selected_molecule_id,
    )


@router.post("/depict")
def chem_depict(body: DepictRequest, user: User = Depends(get_current_user)):
    _ = user
    return depict(body.smiles)


@router.get("/structures/{pdb_id}")
def chem_structure(pdb_id: str, user: User = Depends(get_current_user)):
    _ = user
    pid = pdb_id.upper().strip()
    if len(pid) != 4:
        raise HTTPException(status_code=400, detail="Invalid PDB ID")
    return {
        "pdb_id": pid,
        "mmcif_url": rcsb_mmcif_url(pid),
        "viewer_url": molstar_viewer_url(pdb_id=pid),
        "rcsb_url": f"https://www.rcsb.org/structure/{pid}",
    }


@router.post("/session/import")
def import_chem_session(body: ImportRequest, user: User = Depends(get_current_user)):
    try:
        return session_store.import_session(body.model_dump(exclude_none=True), user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/session/{session_id}/selection")
def select_chem_entity(session_id: str, body: SelectionRequest, user: User = Depends(get_current_user)):
    _ = user
    updated = session_store.set_selection(
        session_id,
        molecule_id=body.molecule_id,
        pdb_id=body.pdb_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated.get("selection")


@router.get("/session/{session_id}/export")
def chem_export(session_id: str, format: str = "markdown", user: User = Depends(get_current_user)):
    _ = user
    if format not in ("markdown", "md", "json"):
        raise HTTPException(status_code=400, detail="format must be markdown or json")
    if format == "json":
        package = export_session_json(session_id)
        if not package:
            raise HTTPException(status_code=404, detail="Session not found")
        return package
    md = export_session_markdown(session_id)
    if md.startswith("# Session not found"):
        raise HTTPException(status_code=404, detail="Session not found")
    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="mds-session-{session_id[:8]}.md"'},
    )
