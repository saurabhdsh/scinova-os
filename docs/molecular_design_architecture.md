# Molecular Design Architecture — How SciNova Designs Molecules

**Product:** Molecular Discovery Studio  
**Capability:** C3 — Neural Molecule Generation  
**Related:** [`molecular_discovery_studio_features.md`](molecular_discovery_studio_features.md)

This document explains **every step** of molecule design in SciNova: databases, target resolution, neural generation, validation, drug matching, ranking, and visualization.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SciNova UI — Molecular Discovery Studio              │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐  │
│  │  Natural-language query      │    │  Result card                 │  │
│  │  e.g. Design 10 molecules    │    │  candidates · method ·       │  │
│  │  against 3UGC / P_0          │    │  drug match · 2D / 3D        │  │
│  └──────────────┬───────────────┘    └──────────────▲───────────────┘  │
└─────────────────┼───────────────────────────────────┼──────────────────┘
                  │                                   │
                  ▼                                   │
┌─────────────────────────────────┐                   │
│  Orchestrator                   │                   │
│  ┌───────────────────────────┐  │                   │
│  │ Intent classifier → C3    │  │                   │
│  ├───────────────────────────┤  │                   │
│  │ Session: target · PDB ·   │  │                   │
│  │ pocket · actives · cands  │  │                   │
│  └─────────────┬─────────────┘  │                   │
└────────────────┼────────────────┘                   │
                 │                                    │
                 ▼                                    │
┌─────────────────────────────────────────────────────┤
│  Target & structure intel                           │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ Gene /   │──▶│ UniProt  │──▶│ RCSB PDB │        │
│  │ protein  │   │ accession│   │ structures│        │
│  │ extract  │   │ name     │   │ ligands  │        │
│  └──────────┘   │ function │   └────┬─────┘        │
│                 └────┬─────┘        │              │
│                      │              ▼              │
│                      │         ┌──────────┐        │
│                      │         │ Pocket / │        │
│                      │         │ P_0 score│        │
│                      ▼         └────┬─────┘        │
│                 ┌──────────┐        │              │
│                 │ ChEMBL   │        │              │
│                 │ actives  │        │              │
│                 └────┬─────┘        │              │
└──────────────────────┼──────────────┼──────────────┘
                       │              │
                       └──────┬───────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Neural molecule generation                                             │
│                                                                         │
│  ┌────────────────────┐      ┌────────────────────────────────────┐    │
│  │ SMILES corpus      │─────▶│ SciNova SMILES Char-RNN            │    │
│  │ ~4K drug-like      │      │ NumPy · 160-d hidden · 50 epochs   │    │
│  │ (ChEMBL + curated) │      │                                    │    │
│  └────────────────────┘      └───────────────┬────────────────────┘    │
│                                              │                          │
│                    ┌─────────────────────────┼─────────────────────┐   │
│                    ▼                         ▼                     ▼   │
│         ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐ │
│         │ PRIMARY          │   │ SECONDARY        │   │ FALLBACK     │ │
│         │ Neural analog    │   │ Free RNN sample  │   │ Curated      │ │
│         │ R-groups +       │   │ IDs: RNN-01…     │   │ scaffolds +  │ │
│         │ Murcko scaffolds │   │                  │   │ Me / F edits │ │
│         │ IDs: RNN-A01…    │   │                  │   │              │ │
│         └────────┬─────────┘   └────────┬─────────┘   └──────┬───────┘ │
└──────────────────┼──────────────────────┼────────────────────┼─────────┘
                   └──────────────────────┼────────────────────┘
                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Chemistry engine — RDKit                                               │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────────┐ │
│  │ Sanitize / │──▶│ Properties │──▶│ Morgan FP  │──▶│ 2D SVG depict  │ │
│  │ canonicalize│  │ MW cLogP   │   │ r=2 2048b  │   │                │ │
│  │ valence    │   │ QED Lipinski│  │            │   │                │ │
│  └────────────┘   └────────────┘   └─────┬──────┘   └────────────────┘ │
└──────────────────────────────────────────┼──────────────────────────────┘
                                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Drug benchmarking                                                      │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐ │
│  │ Known-drug panel │──▶│ Tanimoto         │──▶│ Analog window        │ │
│  │ JAK / EGFR /     │   │ similarity       │   │ 0.35–0.70 accept     │ │
│  │ GLP1R + generics │   │                  │   │ ≥0.95 drop duplicate │ │
│  └──────────────────┘   └──────────────────┘   └──────────┬───────────┘ │
└───────────────────────────────────────────────────────────┼─────────────┘
                                                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Ranking                                                                │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │ If PDB / pocket named:         │  │ Else:                          │ │
│  │ Docking-score SURROGATE        │  │ Rank by drug-likeness /        │ │
│  │ (QED · MW · cLogP heuristic)   │  │ analog-window proximity        │ │
│  └────────────────┬───────────────┘  └────────────────┬───────────────┘ │
└───────────────────┼───────────────────────────────────┼─────────────────┘
                    └───────────────────┬───────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Visualization                                                          │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │ Native Mol* (SciNova canvas)   │  │ RDKit 2D depiction             │ │
│  │ protein · spin/rock · reps     │  │ candidate SMILES               │ │
│  └────────────────────────────────┘  └────────────────────────────────┘ │
│                              │                                          │
│                              ▼                                          │
│                    Result card (back to UI)                             │
└─────────────────────────────────────────────────────────────────────────┘
```
---

## End-to-end pipeline (step by step)

SciNova follows:

**Target → protein structure → pocket → known drugs → neural generation → chemical validation → drug similarity → ranking → visualization → synthesis assessment**

---

### 1. User defines the design objective

Example query:

> Design 10 small molecules against JAK2 structure 3UGC that bind to pocket P_0.

SciNova extracts:

| Field | Example |
|-------|---------|
| Target | `JAK2` |
| Protein structure | `3UGC` |
| Pocket | `P_0` |
| Count | `10` |
| Task | Receptor-based molecule design |

The orchestrator classifies this as **C3 — Neural Molecule Generation** and carries forward session context (target, PDB, pocket, known actives, prior candidates).

---

### 2. Target identification

Natural-language names map to gene symbols:

| User phrasing | Gene |
|---------------|------|
| Janus kinase 2 | `JAK2` |
| Janus kinase 1 | `JAK1` |
| GLP-1 receptor | `GLP1R` |

**Database: UniProt**

| Field | JAK2 example |
|-------|--------------|
| Gene | `JAK2` |
| UniProt | `O60674` |
| Protein | Tyrosine-protein kinase JAK2 |
| Organism | Homo sapiens |
| Function | Cytokine signalling via JAK–STAT |

Curated fallbacks exist if UniProt is unreachable (`KNOWN_TARGETS` in `target_intel.py`).

**Module:** `backend/app/services/chem/target_intel.py`

---

### 3. Protein structure selection

**Database: RCSB Protein Data Bank**

Using the UniProt accession, SciNova fetches a structure catalogue:

- PDB ID
- Experimental method
- Resolution (Å)
- Structure title
- Co-crystallized ligands
- Total filtered count

Default filters:

- Co-crystal ligand present
- Resolution ≤ 2.5 Å

Example selection: **`3UGC`** (JAK2).

Structures open in-canvas via native **Mol\*** (cartoon, surface, ball & stick, spacefill).

**Modules:** `pdb_catalog.py`, `structure_dossier.py`, `MolStarCanvas.jsx`

---

### 4. Pocket and druggability analysis

Example:

> Analyze the binding pockets of 3UGC.

Returns:

- Pocket ID (e.g. `P_0`)
- Druggability score
- Pocket rank
- Ligand context
- Narrative

**Honest boundary:** `3UGC` uses a curated demo pocket map. Other PDBs use a ligand/resolution heuristic — not a full geometric detector (FPocket / P2Rank).

**Module:** `pocket_analysis.py`

---

### 5. Known bioactive compounds

**Database: ChEMBL**

| Field | Use |
|-------|-----|
| ChEMBL ID | Compound identity |
| Preferred name | Drug / chemotype label |
| SMILES | Structure for fingerprints & variants |
| pChEMBL | Activity strength |
| Assay | Context |

JAK2 examples: Ruxolitinib, Fedratinib, Pacritinib, Momelotinib, Abrocitinib.

Offline: curated demo actives in `chembl_client.py`.

**Module:** `chembl_client.py`

---

### 6. Neural model

**Name:** SciNova SMILES Char-RNN  
**Implementation:** NumPy character-level RNN

| Parameter | Value |
|-----------|--------|
| Training data | **~4,000 drug-like SMILES** (curated seeds + ChEMBL small molecules, filtered) |
| Hidden size | 160 |
| Epochs | 50 |
| Representation | SMILES strings |
| Weights | `models/smiles_char_rnn.npz` + `.json` |
| Corpus file | `data/druglike_smiles.txt` |

The network predicts the next SMILES character given prior characters, learning patterns such as aromatic rings, amides, heterocycles, branches, and ring closures.

This is a **trained neural sampler** at MVP scale (~4K molecules). Expanding from ~200 → ~4K improves validity and drug-like character of free samples, but it is still **not** a large industrial generative model (those often train on 10⁵–10⁶+ molecules with graph/transformer architectures).

#### Will ~4K give “good” results?

| Expectation | Reality |
|-------------|---------|
| Better free RNN samples than ~200 | **Yes** — more valid, more drug-like character patterns |
| Molecules that look like real medchem | **Mostly via analog route** (scaffold + neural R-group), which already anchors to approved drugs |
| Competitive with large pharma generative AI | **No** — Char-RNN + 4K is a demo-strength model |
| Real binding to a named pocket | **No** — still needs docking / structure-based scoring |
| Useful SciNova demo / MVP | **Yes** — especially with drug-similarity gating |

**Modules:** `smiles_rnn.py`, `smiles_corpus.py`, `corpus_builder.py`, `scripts/train_smiles_rnn.py`, `scripts/build_smiles_corpus.py`

---

### 7. Generation routes

```
PRIMARY — Neural drug-analog design
┌─────────────────┐     ┌─────────────────┐
│ Known drugs for │────▶│ Murcko scaffolds│
│ target family   │     │ (RDKit)         │
└─────────────────┘     └────────┬────────┘
                                 │
┌─────────────────┐              │
│ RNN samples     │              │
│ R-group frags   │──────┐       │
└─────────────────┘      │       │
                         ▼       ▼
                  ┌─────────────────────┐
                  │ Graft fragment onto │
                  │ scaffold (RDKit)    │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ Accept if Tanimoto  │
                  │ 0.35–0.70 and not   │
                  │ a duplicate         │
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │ IDs: RNN-A01, A02…  │
                  └─────────────────────┘


SECONDARY — Free neural sampling
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ RNN samples     │────▶│ Chemotype prime │────▶│ IDs: RNN-01…    │
│ full SMILES     │     │ (JAK / GLP)     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘


FALLBACK — Curated scaffolds
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Curated scaffold│────▶│ Me / F variants │────▶│ IDs: DSN-… /    │
│ pool            │     │                 │     │ REF-…           │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```
#### Primary — neural drug-analog design

1. Select known drugs for the target family (75% family-biased, 25% broader).
2. Extract Bemis–Murcko scaffolds with RDKit.
3. Sample short R-group fragments from the Char-RNN.
4. Attach fragments to open C/N sites on the scaffold.
5. Sanitize; keep only molecules inside the drug-similarity window.
6. Record parent drug, neural fragment, SMILES, closest drug, similarity.

#### Secondary — free neural sampling

Full SMILES from the RNN, with mild JAK/GLP prefixes (e.g. `CN1CCN`, `O=C(Nc`). Increases diversity; may be less drug-like than analogs.

#### Fallback

If neural routes under-fill the requested count: curated scaffolds + session ChEMBL SMILES + conservative Me/F edits.

**Modules:** `analog_design.py`, `molecule_design.py`, `smiles_rnn.py`

---

### 8. RDKit chemical validation

Every SMILES must pass:

- Parse & sanitize
- Valence and ring-closure checks
- Canonical SMILES
- Duplicate removal
- Heavy-atom gates (prefer ≥14; free samples may relax to ≥10; reject &gt;60; analogs 14–55)

Invalid neural strings never appear in the final table.

---

### 9. Molecular properties

| Property | Meaning |
|----------|---------|
| MW | Size |
| cLogP | Lipophilicity |
| TPSA | Polar surface area |
| HBD / HBA | H-bond donors / acceptors |
| Rings | Ring count |
| QED | Drug-likeness estimate |
| Lipinski | Oral-drug rule screen |

These indicate chemical plausibility — not experimental activity or safety.

---

### 10. Matching against existing drugs

**Fingerprints:** Morgan radius 2, 2048 bits  
**Metric:** Tanimoto similarity

**Reference panel** (`drug_similarity.py`):

- Target-family drugs (JAK, EGFR, GLP1R, …)
- Generic approved / clinical panel
- Optional session ChEMBL actives

Typical JAK2 run: ~28 reference structures.

| Similarity | Verdict |
|------------|---------|
| &lt; 0.35 | Novel chemotype / low drug similarity |
| 0.35–0.70 | **Drug-like analog window** (preferred) |
| 0.70–0.85 | Close analog |
| 0.85–0.95 | Very close analog |
| ≥ 0.95 | Duplicate → **rejected** |

The 0.35–0.70 window is a **design heuristic**. It does not prove patentability, biological activity, or safety.

**Module:** `drug_similarity.py`

---

### 11. Ranking

| Context | Method |
|---------|--------|
| PDB + pocket named | Docking-score **surrogate** (QED, MW, cLogP, mild chemotype bias). More negative = better rank |
| No structure | Rank by proximity to the analog window + drug similarity |

**Honest boundary:** the surrogate is **not** AutoDock Vina / real pose scoring. The PDB and pocket set design context; ranking remains property-based.

---

### 12. Result card contents

Table columns (as available):

- Rank · Candidate ID · Surrogate docking score  
- MW · cLogP · QED  
- Built on (scaffold parent) · Closest drug · Similarity · Verdict · SMILES  

Method panel steps:

1. Train on chemical data  
2. Sample candidate structures  
3. Graft neural R-groups onto approved-drug scaffolds  
4. Validate & featurize  
5. Match against existing drugs  
6. Rank for the design goal  

**Frontend:** `ChemResultCard.jsx`

---

### 13. Visualization

| Asset | Tool |
|-------|------|
| 2D molecule drawing | RDKit SVG (`SmilesDepict.jsx`) |
| 3D protein | Native Mol\* in SciNova (`MolStarCanvas.jsx`) |
| Animation | Spin / Rock |
| Representations | Cartoon · Surface · Ball & stick · Spacefill |

Mol\* shows the **protein/PDB**. It does not yet show computed docked poses of each generated candidate (docking not implemented).

---

### 14. Downstream capabilities

| Cap | Role |
|-----|------|
| C4 | Novelty vs session actives (Morgan / Tanimoto) |
| C5 | Motif / SAR-style medicinal chemistry reasoning |
| C7 | Rule-based synthetic feasibility |
| C8 | Reasoning trace + Markdown session export |

---

## Databases & tools summary

| System | Role in design |
|--------|----------------|
| **UniProt** | Target identity, accession, function |
| **RCSB PDB** | Crystal structures, resolution, ligands |
| **ChEMBL** | Known bioactive SMILES / activities |
| **Local SMILES corpus** | Char-RNN training data |
| **Local known-drug panel** | Fast drug-similarity benchmarking |
| **RDKit** | Validation, descriptors, fingerprints, scaffolds, 2D |
| **NumPy Char-RNN** | Neural SMILES / fragment sampling |
| **Mol\*** | In-canvas 3D protein visualization |
| **Session store** | In-memory design context across queries |

---

## Code map

| Module | Responsibility |
|--------|----------------|
| `orchestrator.py` | Intent routing, session, C3 trigger |
| `target_intel.py` | Gene → UniProt |
| `pdb_catalog.py` | Filtered PDB list |
| `structure_dossier.py` | Per-PDB dossier |
| `pocket_analysis.py` | Pocket / druggability |
| `chembl_client.py` | Known actives |
| `smiles_corpus.py` | Training SMILES |
| `smiles_rnn.py` | Train / sample / fragment sample |
| `analog_design.py` | Scaffold + neural R-group grafting |
| `drug_similarity.py` | Reference drugs + Tanimoto verdicts |
| `molecule_design.py` | C3 orchestration, properties, ranking |
| `structure_assets.py` | 2D / Mol\* payload helpers |
| `MolecularDiscoveryStudio.jsx` | Studio page |
| `ChemResultCard.jsx` | Candidate & method UI |
| `MolStarCanvas.jsx` | Native 3D viewer |

---

## What the system proves vs does not prove

### Proves

- Valid chemical graph (RDKit)
- Computationally generated / modified structure
- Calculable drug-like properties
- Not an exact copy of the local reference-drug panel
- Measurable similarity to known drugs
- Consistent ranking for comparison inside SciNova

### Does not yet prove

- Binding to `3UGC` / pocket `P_0`
- Experimental potency or selectivity
- ADMET / safety
- Synthetic success in the lab
- Legal patentability
- Clinical viability

Those need real docking (e.g. AutoDock Vina), dynamics, ADMET models, retrosynthesis engines, and wet-lab validation.

---

## Example demo path

1. *What are the available crystal structures of janus kinase 2 in the PDB?*  
2. *Retrieve the PDB structure of 3UGC*  
3. *Analyze druggability / binding pockets of 3UGC*  
4. *Design 10 small molecules against 3UGC that bind to pocket P_0*  
5. Continue with ChEMBL actives → novelty → motifs → synthesis → export  

---

## Related docs

- Features inventory: [`molecular_discovery_studio_features.md`](molecular_discovery_studio_features.md)  
- Demo script: [`demo_molecular_discovery_studio.md`](demo_molecular_discovery_studio.md)  
