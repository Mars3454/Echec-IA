"""
weights.py - gestion des poids d'évaluation et de la "meilleure génération".

But:
- Permettre à l'IA de charger des poids depuis /generations (apprentissage).
- L'entraînement (tools/train_generations.py) crée des fichiers weights_gen_X.json.
- best.json indique quel fichier est la meilleure génération.

Format weights_gen_X.json (exemple):
{
  "version": 1,
  "name": "gen_12",
  "created_at": "2026-02-08T20:00:00",
  "weights": {
    "center_main": 20,
    "center_ext": 5,
    "develop": 15,
    "castled": 30,
    "queen_early": 10,
    "mobility": 1,
    "in_check": 25
  }
}
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import json
import os
from datetime import datetime

DEFAULT_WEIGHTS = {
    "center_main": 20,
    "center_ext": 5,
    "develop": 15,
    "castled": 30,
    "queen_early": 10,
    "mobility": 1,
    "in_check": 25,
}

def project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generations_dir() -> str:
    return os.path.join(project_root(), "generations")

def best_path() -> str:
    return os.path.join(generations_dir(), "best.json")

def gen_path(n: int) -> str:
    return os.path.join(generations_dir(), f"weights_gen_{n}.json")

def ensure_defaults() -> None:
    os.makedirs(generations_dir(), exist_ok=True)
    # gen_0
    p0 = gen_path(0)
    if not os.path.exists(p0):
        save_gen(p0, 0, DEFAULT_WEIGHTS, name="gen_0")
    # best.json
    if not os.path.exists(best_path()):
        set_best(p0)

def save_gen(path: str, gen_id: int, weights: Dict[str, int], name: Optional[str]=None) -> None:
    payload = {
        "version": 1,
        "name": name or f"gen_{gen_id}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "weights": {k:int(v) for k,v in weights.items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def load_gen(path: str) -> Dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    w = data.get("weights", {})
    # fallback defaults
    merged = dict(DEFAULT_WEIGHTS)
    for k,v in w.items():
        merged[k] = int(v)
    return merged

def get_best_weights() -> Dict[str, int]:
    ensure_defaults()
    with open(best_path(), "r", encoding="utf-8") as f:
        data = json.load(f)
    p = data.get("path")
    if not p or not os.path.exists(p):
        # fallback to gen_0
        p = gen_path(0)
        set_best(p)
    return load_gen(p)

def get_best_file() -> str:
    ensure_defaults()
    with open(best_path(), "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("path") or gen_path(0)

def set_best(weights_file: str) -> None:
    with open(best_path(), "w", encoding="utf-8") as f:
        json.dump({"path": os.path.abspath(weights_file)}, f, indent=2)

def latest_generation_index() -> int:
    ensure_defaults()
    i = 0
    while os.path.exists(gen_path(i+1)):
        i += 1
    return i
