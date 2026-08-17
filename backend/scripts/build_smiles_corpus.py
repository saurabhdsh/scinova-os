#!/usr/bin/env python3
"""Build a 3–5K drug-like SMILES corpus from ChEMBL (+ curated seeds).

Writes: backend/app/services/chem/data/druglike_smiles.txt

Usage:
  python backend/scripts/build_smiles_corpus.py --target 4000
  # or inside Docker:
  docker compose exec backend python -c "from app.services.chem.corpus_builder import build_expanded_corpus; build_expanded_corpus(4000)"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from app.services.chem.corpus_builder import build_expanded_corpus  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=4000, help="Target SMILES count (3K–5K)")
    args = ap.parse_args()
    path = build_expanded_corpus(args.target)
    print(f"Corpus ready: {path}")


if __name__ == "__main__":
    main()
