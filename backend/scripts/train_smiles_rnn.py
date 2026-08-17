#!/usr/bin/env python3
"""Retrain the SciNova SMILES char-RNN and write weights under chem/models/.

Usage (from repo root, with numpy + rdkit available):
  python backend/scripts/build_smiles_corpus.py --target 4000
  python backend/scripts/train_smiles_rnn.py
  python backend/scripts/train_smiles_rnn.py --epochs 50 --hidden 160
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from app.services.chem.smiles_corpus import get_training_smiles  # noqa: E402
from app.services.chem.smiles_rnn import save_model, train_char_rnn  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--hidden", type=int, default=160)
    ap.add_argument("--lr", type=float, default=0.04)
    args = ap.parse_args()

    smiles = get_training_smiles()
    print(f"Training on {len(smiles)} SMILES · H={args.hidden} · epochs={args.epochs}…")
    model = train_char_rnn(
        smiles,
        epochs=args.epochs,
        hidden_size=args.hidden,
        learning_rate=args.lr,
        seed=11,
    )
    save_model(model)
    print(
        f"Saved · loss={model['smooth_loss']:.3f} · vocab={len(model['vocab'])} · "
        f"H={model['hidden_size']} · epochs={model['epochs']} · n={model['n_train_smiles']}"
    )


if __name__ == "__main__":
    main()
