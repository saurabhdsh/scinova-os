# Molecular Discovery Studio — Features Built

**Product:** Molecular Discovery Studio  
**Nav / route:** `/molecular-studio`  
**Stack:** FastAPI chem services + React Studio UI + native Mol\* (in SciNova canvas)

This page summarizes what was implemented in SciNova for computational chemistry discovery (target → structure → pocket → design → explainability).

---

## Product surface

| Item | Detail |
|------|--------|
| Page | Molecular Discovery Studio — session + result cards |
| Layout | Two-column: composer (left) + full-height results (right) |
| Session | In-memory session carries target, PDB, actives, candidates, last SMILES |
| Explainability | Collapsible **Reasoning Trace** on every card (tools, parameters, observations) |
| Export | Markdown session export (C8) |
| KG bridge | “Open in Molecular Discovery Studio” from protein/target/compound nodes |

---

## Capabilities (C1–C8 + extensions)

### C1 — Target Intelligence
- Resolve gene / protein name → UniProt (e.g. “janus kinase 2” → **JAK2** / **O60674**)
- PDB catalog via RCSB with filters: **co-crystal ligand** + **resolution ≤ 2.5 Å**
- **Total filtered count** (e.g. ~151 for JAK2) plus representative table
- Table columns: PDB ID, Resolution (Å), Method, Title
- Clickable PDB badges load 3D in-canvas

### C2 — Known Bioactive Discovery
- ChEMBL actives for the session target
- Table: ChEMBL ID, name, pChEMBL, assay, SMILES
- 2D depiction of top active

### C3 — Molecule Design (neural generator, drug-benchmarked)
- **SciNova SMILES Char-RNN** — character-level neural net trained on **~4,000 drug-like SMILES** (ChEMBL small molecules + curated seeds; filtered by RDKit MW / heavy atoms / Lipinski-ish gates)
- Hidden size **160**, **50** epochs; weights in `models/smiles_char_rnn.*`
- **Neural analog design (primary route):** the RNN samples R-group fragments, which RDKit grafts
  onto Murcko scaffolds of approved drugs for that target family (`RNN-A…` IDs). This keeps the
  generated chemistry medicinally plausible instead of drifting into exotic chemotypes.
- **Free neural sampling (secondary route):** unconditioned RNN samples for chemotype diversity (`RNN-…` IDs)
- Every candidate is fingerprinted (Morgan r=2, 2048 bits) and compared with approved / clinical drugs:
  - **Closest drug**, **Tanimoto similarity**, and a **verdict** are shown per molecule
  - Exact duplicates of known drugs are **rejected**, so output is always new matter
  - Acceptance window **0.35–0.70** — drug-like enough to be credible, novel enough to be patentable
- Mild chemotype priming for JAK / GLP families and named PDB / pocket designs
- Scaffold pool used only as a **fallback** if sampling yields too few valid molecules
- Ranked with a docking-score surrogate when a PDB/pocket is named, otherwise by proximity to the analog window
- Example: *Design 10 small molecules against 3UGC that bind to pocket P_0*

### C4 — Chemical Novelty
- Morgan fingerprints + Tanimoto vs known actives
- Novelty labels + closest analog

### C5 — Medicinal Chemistry Reasoning
- Motif / SAR-style matrix for candidates
- Optional literature-style references when available

### C6 — Molecular Visualization
- **Native Mol\*** inside SciNova (not an external molstar.org page)
- Controls: Static / Spin / Rock, Cartoon / Surface / Ball & stick / Spacefill, color themes
- Reset camera, PNG snapshot, fullscreen
- Structure details: Entry, Chains, Residues, Atoms, Ligand present/absent
- **RDKit 2D SVG** depiction (requires X11 libs: libxrender, libxext, libsm, libexpat)

### C6D — Structure Dossier
- Retrieve a named PDB entry (e.g. **3UGC**)
- Overview: title, resolution, experimental method
- Ligand table (comp ID + chemical name)
- In-canvas Mol\* view
- Example: *Retrieve the PDB structure of 3UGC*

### C6P — Pocket / Druggability
- Binding-site / druggability analysis for a PDB
- Top pocket score (e.g. **P_0 · 0.88** for 3UGC) + pocket table
- Curated map for demo entries; heuristic fallback otherwise
- Example: *Analyze druggability / binding pockets of 3UGC*

### C7 — Synthetic Feasibility
- Rule-based route / complexity estimate for top molecule

### C8 — Scientific Explainability / Capture
- Session snapshot + markdown export for review

---

## Backend modules

| Module | Role |
|--------|------|
| `backend/app/routes/chem.py` | REST API (`/api/chem/...`) |
| `backend/app/services/chem/orchestrator.py` | Intent routing + session orchestration |
| `backend/app/services/chem/target_intel.py` | C1 gene/protein → UniProt |
| `backend/app/services/chem/pdb_catalog.py` | Filtered PDB list + enrichment |
| `backend/app/services/chem/structure_dossier.py` | Per-entry dossier + ligands |
| `backend/app/services/chem/pocket_analysis.py` | Pocket / druggability |
| `backend/app/services/chem/chembl_client.py` | C2 actives |
| `backend/app/services/chem/molecule_design.py` | C3 neural + scaffold design |
| `backend/app/services/chem/smiles_rnn.py` | Char-RNN train / sample / load / fragment sampling |
| `backend/app/services/chem/analog_design.py` | Neural R-groups grafted onto approved-drug scaffolds |
| `backend/app/services/chem/drug_similarity.py` | Known-drug reference set + Tanimoto verdicts |
| `backend/app/services/chem/smiles_corpus.py` | Chemical SMILES training seeds |
| `backend/app/services/chem/corpus_builder.py` | ChEMBL fetch → `data/druglike_smiles.txt` (~4K) |
| `backend/app/services/chem/data/druglike_smiles.txt` | Expanded drug-like training corpus |
| `backend/app/services/chem/models/smiles_char_rnn.*` | Trained weights + metadata |
| `backend/app/services/chem/novelty.py` | C4 |
| `backend/app/services/chem/medchem_reasoning.py` | C5 |
| `backend/app/services/chem/structure_assets.py` | C6 assets / RDKit depict |
| `backend/app/services/chem/retrosynthesis.py` | C7 |
| `backend/app/services/chem/session_store.py` | Session state |
| Tool Fabric | UniProt, RCSB PDB, ChEMBL, Mol\* catalog entries |

---

## Frontend modules

| Module | Role |
|--------|------|
| `frontend/src/pages/MolecularDiscoveryStudio.jsx` | Studio page + suggestions |
| `frontend/src/components/chem/ChemResultCard.jsx` | Result cards (tables, dossier, pockets, method, trace) |
| `frontend/src/components/chem/MolStarViewer.jsx` | Lazy-loaded Mol\* wrapper |
| `frontend/src/components/chem/MolStarCanvas.jsx` | Native Mol\* engine + animation / reps |
| `frontend/src/components/chem/SmilesDepict.jsx` | 2D SVG depiction |
| `frontend/src/components/chem/ChemSessionBar.jsx` | Session summary + export |
| Nav / palette / App route | Discovery → Molecular Discovery Studio |

---

## Suggested demo path (matches AIDD-style screenshots)

1. *What are the available crystal structures of janus kinase 2 in the Protein Data Bank (PDB)?*  
2. *Retrieve the PDB structure of 3UGC*  
3. *Analyze druggability / binding pockets of 3UGC*  
4. *Design 10 small molecules against 3UGC that bind to pocket P_0*  
5. Continue with ChEMBL actives → novelty → motifs → synthesis → export  

---

## Honest MVP boundaries

- Pocket analysis for non-demo PDBs is heuristic (ligand + resolution); **3UGC** uses a curated pocket map.
- “Docking scores” in RBDD are a **surrogate** (property / chemotype ranking), not a full AutoDock Vina campaign.
- Molecule invention uses a **trained SMILES char-RNN** on **~4K drug-like SMILES** (not a pocket-conditioned 3D generative model). Validity is enforced by RDKit.
- External APIs (UniProt, RCSB, ChEMBL) have curated fallbacks when offline.
- Session store is in-memory (resets on backend restart).

---

## Related docs

- Design architecture (databases, model, diagrams): [`molecular_design_architecture.md`](molecular_design_architecture.md)
- Demo script: [`demo_molecular_discovery_studio.md`](demo_molecular_discovery_studio.md)
