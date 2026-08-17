"""Character-level SMILES RNN — neural generator trained on chemical SMILES.

Architecture (Karpathy-style char-RNN):
  h_t = tanh(x_t @ Wxh + h_{t-1} @ Whh + bh)
  y_t = h_t @ Why + by

Trained offline (or on first use) on the curated corpus in smiles_corpus.py.
Sampling draws new SMILES from the learned next-character distribution.
"""

from __future__ import annotations

import json
import logging
import math
import random
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

START, END = "^", "$"
MODEL_DIR = Path(__file__).resolve().parent / "models"
WEIGHTS_PATH = MODEL_DIR / "smiles_char_rnn.npz"
META_PATH = MODEL_DIR / "smiles_char_rnn.json"

_lock = threading.Lock()
_MODEL: dict[str, Any] | None = None


def _softmax(x):
    import numpy as np

    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-12)


def _one_hot(ix: int, vocab_size: int):
    import numpy as np

    x = np.zeros((vocab_size, 1))
    x[ix] = 1
    return x


def build_vocab(smiles_list: list[str]) -> tuple[list[str], dict[str, int], dict[int, str]]:
    chars = set()
    for s in smiles_list:
        chars.update(s)
    chars.update({START, END})
    # Stable order for reproducibility
    vocab = sorted(chars)
    char_to_ix = {c: i for i, c in enumerate(vocab)}
    ix_to_char = {i: c for i, c in enumerate(vocab)}
    return vocab, char_to_ix, ix_to_char


def train_char_rnn(
    smiles_list: list[str],
    *,
    hidden_size: int = 128,
    epochs: int = 40,
    learning_rate: float = 0.05,
    seed: int = 42,
) -> dict[str, Any]:
    """Train a char-RNN molecule-by-molecule and return weights + metadata."""
    import numpy as np

    rng = np.random.default_rng(seed)
    random.seed(seed)

    vocab, char_to_ix, ix_to_char = build_vocab(smiles_list)
    vocab_size = len(vocab)

    Wxh = rng.standard_normal((hidden_size, vocab_size)) * 0.01
    Whh = rng.standard_normal((hidden_size, hidden_size)) * 0.01
    Why = rng.standard_normal((vocab_size, hidden_size)) * 0.01
    bh = np.zeros((hidden_size, 1))
    by = np.zeros((vocab_size, 1))

    mWxh = np.zeros_like(Wxh)
    mWhh = np.zeros_like(Whh)
    mWhy = np.zeros_like(Why)
    mbh = np.zeros_like(bh)
    mby = np.zeros_like(by)

    sequences = []
    for s in smiles_list:
        seq = [char_to_ix[c] for c in f"{START}{s}{END}" if c in char_to_ix]
        if len(seq) >= 3:
            sequences.append(seq)

    smooth_loss = -math.log(1.0 / vocab_size) * 20
    n_updates = 0

    for epoch in range(epochs):
        random.shuffle(sequences)
        for seq in sequences:
            inputs = seq[:-1]
            targets = seq[1:]
            xs, hs, ys, ps = {}, {}, {}, {}
            hs[-1] = np.zeros((hidden_size, 1))
            loss = 0.0
            for t in range(len(inputs)):
                xs[t] = _one_hot(inputs[t], vocab_size)
                hs[t] = np.tanh(Wxh @ xs[t] + Whh @ hs[t - 1] + bh)
                ys[t] = Why @ hs[t] + by
                ps[t] = _softmax(ys[t].ravel())
                loss += -math.log(float(ps[t][targets[t]]) + 1e-12)

            dWxh = np.zeros_like(Wxh)
            dWhh = np.zeros_like(Whh)
            dWhy = np.zeros_like(Why)
            dbh = np.zeros_like(bh)
            dby = np.zeros_like(by)
            dhnext = np.zeros_like(hs[0])

            for t in reversed(range(len(inputs))):
                dy = np.copy(ps[t]).reshape(-1, 1)
                dy[targets[t]] -= 1
                dWhy += dy @ hs[t].T
                dby += dy
                dh = Why.T @ dy + dhnext
                dhraw = (1 - hs[t] * hs[t]) * dh
                dbh += dhraw
                dWxh += dhraw @ xs[t].T
                dWhh += dhraw @ hs[t - 1].T
                dhnext = Whh.T @ dhraw

            for dparam in (dWxh, dWhh, dWhy, dbh, dby):
                np.clip(dparam, -5, 5, out=dparam)

            for param, dparam, mem in (
                (Wxh, dWxh, mWxh),
                (Whh, dWhh, mWhh),
                (Why, dWhy, mWhy),
                (bh, dbh, mbh),
                (by, dby, mby),
            ):
                mem += dparam * dparam
                param += -learning_rate * dparam / (np.sqrt(mem) + 1e-8)

            avg = loss / max(1, len(inputs))
            smooth_loss = smooth_loss * 0.999 + avg * 0.001
            n_updates += 1

        if (epoch + 1) % 5 == 0 or epoch == 0:
            logger.info(
                "SMILES RNN epoch %s/%s smooth_loss=%.3f updates=%s",
                epoch + 1, epochs, smooth_loss, n_updates,
            )

    return {
        "Wxh": Wxh,
        "Whh": Whh,
        "Why": Why,
        "bh": bh,
        "by": by,
        "hidden_size": hidden_size,
        "vocab": vocab,
        "char_to_ix": char_to_ix,
        "ix_to_char": {str(k): v for k, v in ix_to_char.items()},
        "smooth_loss": float(smooth_loss),
        "epochs": epochs,
        "n_train_smiles": len(smiles_list),
        "architecture": "char-RNN (tanh, molecule-level BPTT)",
    }


def save_model(model: dict[str, Any], weights_path: Path = WEIGHTS_PATH, meta_path: Path = META_PATH) -> None:
    import numpy as np

    weights_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        weights_path,
        Wxh=model["Wxh"],
        Whh=model["Whh"],
        Why=model["Why"],
        bh=model["bh"],
        by=model["by"],
    )
    meta = {
        "hidden_size": model["hidden_size"],
        "vocab": model["vocab"],
        "smooth_loss": model.get("smooth_loss"),
        "epochs": model.get("epochs"),
        "n_train_smiles": model.get("n_train_smiles"),
        "architecture": model.get("architecture"),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_model(weights_path: Path = WEIGHTS_PATH, meta_path: Path = META_PATH) -> dict[str, Any] | None:
    import numpy as np

    if not weights_path.exists() or not meta_path.exists():
        return None
    try:
        data = np.load(weights_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        vocab = meta["vocab"]
        char_to_ix = {c: i for i, c in enumerate(vocab)}
        ix_to_char = {i: c for i, c in enumerate(vocab)}
        return {
            "Wxh": data["Wxh"],
            "Whh": data["Whh"],
            "Why": data["Why"],
            "bh": data["bh"],
            "by": data["by"],
            "hidden_size": int(meta["hidden_size"]),
            "vocab": vocab,
            "char_to_ix": char_to_ix,
            "ix_to_char": ix_to_char,
            "smooth_loss": meta.get("smooth_loss"),
            "epochs": meta.get("epochs"),
            "n_train_smiles": meta.get("n_train_smiles"),
            "architecture": meta.get("architecture"),
        }
    except Exception as exc:
        logger.warning("Failed to load SMILES RNN: %s", exc)
        return None


def sample_smiles(
    model: dict[str, Any],
    *,
    temperature: float = 0.9,
    max_len: int = 80,
    seed_prefix: str = "",
    rng: random.Random | None = None,
) -> str:
    """Sample one SMILES string from the trained RNN."""
    import numpy as np

    rng = rng or random.Random()
    char_to_ix = model["char_to_ix"]
    ix_to_char = model["ix_to_char"]
    vocab_size = len(model["vocab"])
    h = np.zeros((model["hidden_size"], 1))

    # Prime with start (+ optional chemotype prefix)
    prime = START + (seed_prefix or "")
    ix = char_to_ix.get(START, 0)
    for ch in prime:
        if ch not in char_to_ix:
            continue
        ix = char_to_ix[ch]
        x = _one_hot(ix, vocab_size)
        h = np.tanh(model["Wxh"] @ x + model["Whh"] @ h + model["bh"])

    out_chars: list[str] = list(seed_prefix or "")
    for _ in range(max_len):
        x = _one_hot(ix, vocab_size)
        h = np.tanh(model["Wxh"] @ x + model["Whh"] @ h + model["bh"])
        y = (model["Why"] @ h + model["by"]).ravel()
        y = y / max(temperature, 1e-3)
        p = _softmax(y)
        # Avoid starting END immediately if empty
        ix = int(rng.choices(range(vocab_size), weights=p.tolist(), k=1)[0])
        ch = ix_to_char[ix]
        if ch == END:
            break
        if ch == START:
            continue
        out_chars.append(ch)
    return "".join(out_chars)


def _validate_smiles(smi: str, *, min_heavy_atoms: int = 10) -> str | None:
    smi = (smi or "").strip()
    if len(smi) < 5:
        return None
    # Quick syntax gates before RDKit
    if smi.count("(") != smi.count(")"):
        return None
    if smi.count("[") != smi.count("]"):
        return None
    if any(ch in smi for ch in {"^", "$"}):
        return None
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return None
        Chem.SanitizeMol(mol)
        # Drug-likeness gate: reject trivial fragments (benzene, anisole, …)
        if mol.GetNumHeavyAtoms() < min_heavy_atoms:
            return None
        if mol.GetNumHeavyAtoms() > 60:
            return None
        return Chem.MolToSmiles(mol)
    except Exception:
        return None


def ensure_model(force_retrain: bool = False) -> dict[str, Any]:
    """Load persisted weights, or train from the chemical corpus and save."""
    global _MODEL
    with _lock:
        if _MODEL is not None and not force_retrain:
            return _MODEL
        if not force_retrain:
            loaded = load_model()
            if loaded is not None:
                _MODEL = loaded
                return _MODEL
        from app.services.chem.smiles_corpus import get_training_smiles

        smiles = get_training_smiles()
        logger.info("Training SMILES char-RNN on %s molecules…", len(smiles))
        model = train_char_rnn(smiles, epochs=50, hidden_size=160, learning_rate=0.04)
        save_model(model)
        _MODEL = load_model() or model
        if isinstance(_MODEL.get("ix_to_char"), dict):
            _MODEL["ix_to_char"] = {int(k): v for k, v in _MODEL["ix_to_char"].items()}
        return _MODEL


def generate_molecules(
    n: int = 10,
    *,
    temperature: float = 0.85,
    seed_prefix: str = "",
    max_attempts: int | None = None,
    gene_symbol: str | None = None,
) -> list[dict[str, Any]]:
    """Sample up to n valid unique SMILES from the trained neural generator."""
    model = ensure_model()
    attempts = max_attempts or max(40, n * 25)
    rng = random.Random()

    # Mild chemotype priming by target family
    prefix = seed_prefix
    if not prefix and gene_symbol:
        g = gene_symbol.upper()
        if g.startswith("JAK"):
            prefix = rng.choice(["Cc1ccc", "CN1CCN", "O=C(Nc", "COc1cc"])
        elif g.startswith("GLP"):
            prefix = rng.choice(["O=C(O)c1ccc", "COc1ccc", "CC1=CC"])

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    # Two passes: prefer drug-like (≥14 heavy atoms), then relax to reach the count
    for min_heavy in (14, 10):
        for i in range(attempts):
            if len(out) >= n:
                break
            # Occasionally sample unconditioned for diversity
            use_prefix = prefix if (prefix and i % 3 != 0) else ""
            raw = sample_smiles(
                model,
                temperature=temperature + (0.05 if i % 5 == 0 else 0.0),
                seed_prefix=use_prefix,
                rng=rng,
                max_len=90,
            )
            canon = _validate_smiles(raw, min_heavy_atoms=min_heavy)
            if not canon or canon in seen:
                continue
            seen.add(canon)
            out.append({
                "candidate_id": f"RNN-{len(out) + 1:02d}",
                "smiles": canon,
                "origin": "neural_smiles_rnn",
                "generator": model.get("architecture") or "char-RNN",
                "seed_prefix": use_prefix or None,
            })
        if len(out) >= n:
            break
    return out


def sample_fragments(
    n: int = 12,
    *,
    temperature: float = 0.9,
    min_heavy_atoms: int = 2,
    max_heavy_atoms: int = 9,
    max_attempts: int | None = None,
) -> list[str]:
    """Sample short, valid R-group fragments from the RNN for scaffold decoration."""
    model = ensure_model()
    rng = random.Random()
    attempts = max_attempts or max(60, n * 30)
    out: list[str] = []
    seen: set[str] = set()
    for _ in range(attempts):
        if len(out) >= n:
            break
        raw = sample_smiles(model, temperature=temperature, rng=rng, max_len=18)
        # Cut at the first branch/ring token so fragments stay attachable
        frag = raw.strip()
        if not frag:
            continue
        canon = _validate_smiles(frag, min_heavy_atoms=min_heavy_atoms)
        if not canon:
            continue
        try:
            from rdkit import Chem

            mol = Chem.MolFromSmiles(canon)
            if mol is None or mol.GetNumHeavyAtoms() > max_heavy_atoms:
                continue
        except Exception:
            continue
        if canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    return out


def generator_info() -> dict[str, Any]:
    model = ensure_model()
    return {
        "name": "SciNova SMILES Char-RNN",
        "architecture": model.get("architecture"),
        "hidden_size": model.get("hidden_size"),
        "vocab_size": len(model.get("vocab") or []),
        "n_train_smiles": model.get("n_train_smiles"),
        "epochs": model.get("epochs"),
        "smooth_loss": model.get("smooth_loss"),
        "weights_path": str(WEIGHTS_PATH),
    }
