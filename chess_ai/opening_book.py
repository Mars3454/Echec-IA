"""
commentaire général du fichier : 
Ce fichier gère le livre d'ouverture de l'IA
Il contient une collection de lignes d'ouverture connues du monde des échecs 
(Italienne, Sicilienne, Française, Gambit Dame, Londres, etc.)
organisées selon la couleur de l'IA et le premier coup adverse
 Au lieu de calculer pendant les premiers coups, l'IA suit simplement une ligne préenregistrée,
ce qui la rend plus rapide et joue des débuts solides. La ligne est suivie 
jusqu'à 6 demi-coups maximum, et abandonnée si l'adversaire s'en écarte

variables : 

OPENING_PLIES :Nombre maximum de demi-coups couverts par le livre (valeur : 6)
OPENING_LINES :Dictionnaire principal contenant toutes les lignes d'ouverture classées en 5 catégories : "white" (blancs), "black_vs_e4", "black_vs_d4", "black_vs_c4", "black_vs_nf3"
CURRENT_LINE :Variable globale mémorisant la ligne d'ouverture en cours de suivi. Vaut None si aucune ligne n'est choisie ou si on est sorti du livre
 
"""

from __future__ import annotations
from typing import List, Dict
import random
OPENING_PLIES = 6

# --- Lignes complètes (4-6 coups) ---

OPENING_LINES: Dict[str, List[List[str]]] = {

    "white": [
    # Italienne classique
    ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],

    # Scotch
    ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4"],

    # Sicilienne ouverte
    ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4"],

    # Française avance
    ["e2e4", "e7e6", "d2d4", "d7d5", "e4e5"],

    # Gambit Dame refusé
    ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3"],

    # Système Londres (ultra solide)
    ["d2d4", "d7d5", "g1f3", "g8f6", "c1f4"],

    # Anglaise
    ["c2c4", "e7e5", "b1c3", "g8f6", "g2g3"],

    # Réti
    ["g1f3", "d7d5", "c2c4", "e7e6"],
],


    "black_vs_e4": [
    # Sicilienne Najdorf setup simple
    ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4"],

    # Sicilienne classique
    ["e2e4", "c7c5", "g1f3", "b8c6"],

    # Française
    ["e2e4", "e7e6", "d2d4", "d7d5"],

    # Caro-Kann
    ["e2e4", "c7c6", "d2d4", "d7d5"],

    # Défense ouverte e5
    ["e2e4", "e7e5", "g1f3", "b8c6"],
],

    "black_vs_d4": [
    # Gambit Dame refusé
    ["d2d4", "d7d5", "c2c4", "e7e6"],

    # Slave
    ["d2d4", "d7d5", "c2c4", "c7c6"],

    # Est-indienne
    ["d2d4", "g8f6", "c2c4", "g7g6"],

    # Nimzo-lite
    ["d2d4", "g8f6", "c2c4", "e7e6"],
],

    "black_vs_c4": [
    ["c2c4", "e7e5", "b1c3", "g8f6"],
    ["c2c4", "g8f6", "b1c3", "e7e6"],
],

    "black_vs_nf3": [
        ["g1f3", "d7d5", "c2c4", "e7e6"],
        ["g1f3", "g8f6", "c2c4", "g7g6"],
],
}


# Ligne en cours suivie par l’IA
CURRENT_LINE: List[str] | None = None


def reset_line(): 

    """ Remet CURRENT_LINE à None Appelée au début d'une nouvelle partie
      (depuis new_game dans gui.py) ou quand la position diverge de la ligne choisie"""
    global CURRENT_LINE
    CURRENT_LINE = None


def pick_book_move(history: List[str], is_white: bool) -> str | None:
    """Fonction principale du livre. Reçoit la liste des coups déjà joués en notation UCI 
    et un booléen indiquant si c'est au tour des blancs
    Si aucune ligne n'est encore choisie, en sélectionne une aléatoirement 
    dans la catégorie appropriée selon le premier coup adverse
    Si une ligne est en cours et que l'historique lui correspond exactement, 
    retourne le prochain coup de cette ligne. Si l'adversaire s'est écarté de la ligne, 
    appelle reset_line() et retourne None. Retourne aussi None si on dépasse les 6 demi-coups"""

    
    global CURRENT_LINE

    # Fin forcée du livre
    if len(history) >= OPENING_PLIES:
        reset_line()
        return None

    # Sélection de ligne
    if CURRENT_LINE is None:
        if len(history) == 0 and is_white:
            CURRENT_LINE = random.choice(OPENING_LINES["white"])

        elif len(history) == 1 and not is_white:
            first = history[0]
            if first == "e2e4":
                CURRENT_LINE = random.choice(OPENING_LINES["black_vs_e4"])
            elif first == "d2d4":
                CURRENT_LINE = random.choice(OPENING_LINES["black_vs_d4"])
            elif first == "c2c4":
                CURRENT_LINE = random.choice(OPENING_LINES["black_vs_c4"])
            elif first == "g1f3":
                CURRENT_LINE = random.choice(OPENING_LINES["black_vs_nf3"])
            else:
                return None

    if CURRENT_LINE is None:
        return None

    if len(history) >= len(CURRENT_LINE):
        reset_line()
        return None

    if history == CURRENT_LINE[:len(history)]:
        return CURRENT_LINE[len(history)]

    reset_line()
    return None
