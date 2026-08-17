# Molecular Discovery Studio — Demo Journey (≈3–4 min)

**Product name:** Molecular Discovery Studio (not AIDD)  
**Route:** `/molecular-studio`  
**Login:** `scientist` / `sci123` or `admin` / `admin123`

**Full feature inventory:** [`molecular_discovery_studio_features.md`](molecular_discovery_studio_features.md)

## Scientist journey (C1–C8)

| Step | Say / click suggestion | Capability |
|------|------------------------|------------|
| 1 | Tell me about JAK2 | C1 Target Intelligence + Mol* PDB |
| 2 | Show known JAK2 inhibitors from ChEMBL | C2 Actives table + 2D |
| 3 | Design candidates for this target | C3 Candidates + descriptors |
| 4 | Are these novel vs known inhibitors? | C4 Tanimoto novelty |
| 5 | Which motifs matter and are they present? | C5 Motif matrix + refs |
| 6 | Show this molecule / structure in 3D | C6 Mol* + 2D + shape analogs |
| 7 | Can the top molecule be made? | C7 Route tree |
| 8 | Export this for review | C8 Session export (markdown) |

## Talking points

- Agents decide; **Tool Fabric** instruments (UniProt, RCSB PDB, ChEMBL, RDKit, Mol*) compute.
- **Mol\*** is the C6 structure viewer — not a replacement for Knowledge Graph force-graph.
- Every card has a **collapsible Trace** (specialist, tools, parameters, observations).

## Fallback

If ChEMBL/UniProt are slow offline, curated JAK2/JAK1/GLP1R demos still return structures and actives.
