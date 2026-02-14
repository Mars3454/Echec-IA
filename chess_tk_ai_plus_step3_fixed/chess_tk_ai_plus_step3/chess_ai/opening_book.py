"""
opening_book.py - Petit livre d'ouvertures (UCI moves).
But: donner à l'IA un début plus "humain" + variété, sans calcul.

Structure: dict[tuple(history_uci_moves)] -> list[next_move_uci]
- history est la liste des coups depuis startpos (ex: ["e2e4","c7c5",...])
"""

from __future__ import annotations
from typing import Dict, List, Tuple
import random

BOOK: Dict[Tuple[str, ...], List[str]] = {
    # --- Débuts blancs ---
    (): ["e2e4", "d2d4", "c2c4", "g1f3"],

    # --- Réponses noires à 1.e4 ---
    ("e2e4",): ["c7c5", "e7e5", "e7e6", "c7c6"],

    # Sicilienne: 1.e4 c5
    ("e2e4","c7c5"): ["g1f3", "b1c3"],
    ("e2e4","c7c5","g1f3"): ["d7d6", "e7e6"],
    ("e2e4","c7c5","b1c3"): ["d7d6", "e7e6"],

    # 1.e4 e5
    ("e2e4","e7e5"): ["g1f3", "b1c3", "f1c4"],
    ("e2e4","e7e5","g1f3"): ["b8c6", "d7d6"],
    ("e2e4","e7e5","g1f3","b8c6"): ["f1b5", "f1c4", "d2d4"],  # Espagnole / Italienne / centre

    # Française: 1.e4 e6
    ("e2e4","e7e6"): ["d2d4"],
    ("e2e4","e7e6","d2d4"): ["d7d5"],

    # Caro-Kann: 1.e4 c6
    ("e2e4","c7c6"): ["d2d4"],
    ("e2e4","c7c6","d2d4"): ["d7d5"],

    # --- Réponses noires à 1.d4 ---
    ("d2d4",): ["d7d5", "g8f6", "e7e6"],

    # Gambit Dame: 1.d4 d5 2.c4
    ("d2d4","d7d5"): ["c2c4", "g1f3"],
    ("d2d4","d7d5","c2c4"): ["e7e6", "c7c6", "d5c4"],  # QGD / Slav / acceptée
    ("d2d4","g8f6"): ["c2c4", "g1f3"],
    ("d2d4","g8f6","c2c4"): ["g7g6", "e7e6", "c7c5"],  # Indiennes

    # Anglaise: 1.c4
    ("c2c4",): ["e7e5", "g8f6", "c7c5"],

    # Réti: 1.Nf3
    ("g1f3",): ["d7d5", "g8f6", "c7c5"],
}

def pick_book_move(history: list[str]) -> str | None:
    """Retourne un coup UCI depuis le livre, sinon None."""
    key = tuple(history)
    moves = BOOK.get(key)
    if not moves:
        return None
    return random.choice(moves)
