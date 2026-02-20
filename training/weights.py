"""
commentaire général du fichier : 
Ce fichier est le centre névralgique du système d'entraînement
Il définit les 40 paramètres entraînables de la fonction d'évaluation de 
l'IA (valeurs des pièces, multiplicateurs par phase de jeu, sécurité du roi,
structure de pions, mobilité, centre), leurs valeurs par défaut, leurs
bornes autorisées, et leurs regroupements pour la mutation
Il fournit aussi toutes les fonctions utilitaires de lecture/écriture des
fichiers de poids sur le disque
weights.py - Gestion des poids d'évaluation entraînables.

PARAMÈTRES ENTRAÎNABLES 

Valeurs des pièces (5) :
  pv_pawn, pv_knight, pv_bishop, pv_rook, pv_queen

Multiplicateurs de phase — ouverture (6) :
  op_material, op_center, op_development, op_king_safety,
  op_mobility, op_pawns

Multiplicateurs de phase — milieu de jeu (6) :
  mg_material, mg_center, mg_development, mg_king_safety,
  mg_mobility, mg_pawns

Multiplicateurs de phase — finale (6) :
  eg_material, eg_center, eg_development, eg_king_safety,
  eg_mobility, eg_pawns

Seuils de phase (2) :
  phase_opening_threshold   (nb pièces mineures/majeures → ouverture)
  phase_endgame_threshold   (nb pièces mineures/majeures → finale)

Sécurité du roi (3) :
  ks_attack_penalty         (pénalité par case du roi attaquée)
  ks_castling_bonus         (bonus droit au roque)
  ks_check_bonus            (bonus/malus échec)

Structure de pions (4) :
  pawn_doubled_penalty      (pénalité pion doublé)
  pawn_isolated_penalty     (pénalité pion isolé)
  pawn_passed_bonus         (bonus pion passé)
  pawn_mobility_factor      (facteur mobilité pion)

Finale — roi actif (2) :
  eg_king_activity          (bonus attaques du roi en finale)
  eg_king_centralization    (bonus centralisation roi en finale)

Mobilité (2) :
  mobility_factor           (facteur par coup légal)
  mobility_own_penalty      (malus si mobilité réduite)

Centre (2) :
  center_attack_bonus       (bonus attaque centre principal)
  center_ext_bonus          (bonus attaque centre étendu)

  variables : 
DEFAULT_WEIGHTS ==	Dictionnaire des 40 paramètres avec leurs valeurs de départ. Point de départ de tout entraînement
WEIGHT_BOUNDS == 	Dictionnaire associant à chaque paramètre un tuple (min, max) pour éviter des valeurs absurdes lors des mutations
PARAM_GROUPS == 	Dictionnaire organisant les 40 paramètres en 9 groupes thématiques ("piece_values", "opening", "middlegame", "endgame", "king_safety", "pawns", "mobility", "center", "phase"). Utilisé pour cibler les mutations

"""

from __future__ import annotations
from typing import Dict, Optional
import json, os
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Valeurs par défaut (point de départ de l'entraînement)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_WEIGHTS: Dict[str, float] = {
    # Valeurs des pièces (centipawns)
    "pv_pawn":    100.0,
    "pv_knight":  320.0,
    "pv_bishop":  330.0,
    "pv_rook":    500.0,
    "pv_queen":   900.0,

    # Phase — Ouverture
    "op_material":      1.0,
    "op_center":        1.2,
    "op_development":   1.3,
    "op_king_safety":   0.8,
    "op_mobility":      0.5,
    "op_pawns":         0.6,

    # Phase — Milieu de jeu
    "mg_material":      1.1,
    "mg_center":        1.0,
    "mg_development":   0.7,
    "mg_king_safety":   1.2,
    "mg_mobility":      1.0,
    "mg_pawns":         1.0,

    # Phase — Finale
    "eg_material":      1.3,
    "eg_center":        0.5,
    "eg_development":   0.0,
    "eg_king_safety":   0.6,
    "eg_mobility":      1.2,
    "eg_pawns":         1.4,

    # Seuils de phase
    "phase_opening_threshold":  20.0,
    "phase_endgame_threshold":  10.0,

    # Sécurité du roi
    "ks_attack_penalty":   0.2,
    "ks_castling_bonus":   0.5,
    "ks_check_bonus":      0.5,

    # Structure de pions
    "pawn_doubled_penalty":  0.3,
    "pawn_isolated_penalty": 0.3,
    "pawn_passed_bonus":     0.5,
    "pawn_mobility_factor":  0.05,

    # Finale — roi
    "eg_king_activity":       0.1,
    "eg_king_centralization": 0.05,

    # Mobilité
    "mobility_factor":       0.05,
    "mobility_own_penalty":  0.0,

    # Centre
    "center_attack_bonus":   0.3,
    "center_ext_bonus":      0.1,
}

# Bornes min/max pour chaque paramètre (évite les valeurs absurdes)
WEIGHT_BOUNDS: Dict[str, tuple] = {
    "pv_pawn":    (50.0,   200.0),
    "pv_knight":  (200.0,  500.0),
    "pv_bishop":  (200.0,  500.0),
    "pv_rook":    (300.0,  700.0),
    "pv_queen":   (600.0, 1200.0),

    "op_material":      (0.5, 2.0),
    "op_center":        (0.0, 3.0),
    "op_development":   (0.0, 3.0),
    "op_king_safety":   (0.0, 3.0),
    "op_mobility":      (0.0, 2.0),
    "op_pawns":         (0.0, 2.0),

    "mg_material":      (0.5, 2.0),
    "mg_center":        (0.0, 3.0),
    "mg_development":   (0.0, 2.0),
    "mg_king_safety":   (0.0, 3.0),
    "mg_mobility":      (0.0, 2.0),
    "mg_pawns":         (0.0, 2.0),

    "eg_material":      (0.5, 2.5),
    "eg_center":        (0.0, 2.0),
    "eg_development":   (0.0, 1.0),
    "eg_king_safety":   (0.0, 2.0),
    "eg_mobility":      (0.0, 2.5),
    "eg_pawns":         (0.0, 3.0),

    "phase_opening_threshold":  (12.0, 28.0),
    "phase_endgame_threshold":  (4.0,  16.0),

    "ks_attack_penalty":   (0.0, 1.0),
    "ks_castling_bonus":   (0.0, 2.0),
    "ks_check_bonus":      (0.0, 2.0),

    "pawn_doubled_penalty":  (0.0, 1.0),
    "pawn_isolated_penalty": (0.0, 1.0),
    "pawn_passed_bonus":     (0.0, 2.0),
    "pawn_mobility_factor":  (0.0, 0.2),

    "eg_king_activity":       (0.0, 0.5),
    "eg_king_centralization": (0.0, 0.3),

    "mobility_factor":       (0.0, 0.2),
    "mobility_own_penalty":  (0.0, 0.5),

    "center_attack_bonus":   (0.0, 1.0),
    "center_ext_bonus":      (0.0, 0.5),
}

# Groupes de paramètres pour mutation ciblée (le training choisit un groupe)
PARAM_GROUPS = {
    "piece_values": ["pv_pawn", "pv_knight", "pv_bishop", "pv_rook", "pv_queen"],
    "opening":      [k for k in DEFAULT_WEIGHTS if k.startswith("op_")],
    "middlegame":   [k for k in DEFAULT_WEIGHTS if k.startswith("mg_")],
    "endgame":      [k for k in DEFAULT_WEIGHTS if k.startswith("eg_")],
    "king_safety":  [k for k in DEFAULT_WEIGHTS if k.startswith("ks_")],
    "pawns":        [k for k in DEFAULT_WEIGHTS if k.startswith("pawn_")],
    "mobility":     [k for k in DEFAULT_WEIGHTS if k.startswith("mobility_")],
    "center":       [k for k in DEFAULT_WEIGHTS if k.startswith("center_")],
    "phase":        [k for k in DEFAULT_WEIGHTS if k.startswith("phase_")],
}


# ──────────────────────────────────────────────────────────────────────────────
# Chemins fichiers
# ──────────────────────────────────────────────────────────────────────────────

def project_root() -> str:
    """Retourne le chemin absolu du répertoire racine du projet
      en remontant d'un niveau depuis le répertoire de weights.py"""
    
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def generations_dir() -> str:
    """Retourne le chemin du dossier generations/ où sont stockés tous les fichiers de poids"""
    return os.path.join(project_root(), "generations")

def best_path() -> str:
    """Retourne le chemin du fichier best.json, 
    qui contient uniquement un pointeur (le chemin) vers le meilleur fichier de poids actuellement"""

    return os.path.join(generations_dir(), "best.json")

def gen_path(n: int) -> str:
    """Retourne le chemin du fichier de poids d'une génération précise : generations/weights_gen_N.json"""
    return os.path.join(generations_dir(), f"weights_gen_{n}.json")


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────────────

def clamp_weights(w: Dict[str, float]) -> Dict[str, float]:
    """Prend un dictionnaire de poids et ramène chaque valeur dans ses bornes autorisées selon WEIGHT_BOUNDS 
    Utilisée après chaque mutation pour garantir la validité des poids"""

    out = {}
    for k, v in w.items():
        lo, hi = WEIGHT_BOUNDS.get(k, (-1e9, 1e9))
        out[k] = max(lo, min(hi, float(v)))
    return out


def ensure_defaults() -> None:
    """Garantit l'existence des fichiers nécessaires au démarrage. Crée le dossier generations/ si besoin
     crée weights_gen_0.json avec les valeurs par défaut si absent, 
    et crée best.json pointant vers gen_0 si absent
     Appelée au démarrage de tout module utilisant le système de poids"""
    
    os.makedirs(generations_dir(), exist_ok=True)
    p0 = gen_path(0)
    if not os.path.exists(p0):
        save_gen(p0, 0, DEFAULT_WEIGHTS, name="gen_0")
    if not os.path.exists(best_path()):
        set_best(p0)


def save_gen(path: str, gen_id: int, weights: Dict[str, float],
             name: Optional[str] = None) -> None:
    
    """Sauvegarde un dictionnaire de poids dans un fichier JSON structuré contenant la version (2),
      le nom, la date de création et les poids arrondis à 4 décimales."""
    payload = {
        "version":    2,
        "name":       name or f"gen_{gen_id}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "weights":    {k: round(float(v), 4) for k, v in weights.items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_gen(path: str) -> Dict[str, float]:
    """Charge un fichier de poids JSON et retourne les poids fusionnés avec les valeurs par défaut 
    (si un paramètre est absent du fichier,
      il prend sa valeur par défaut). Applique clamp_weights avant de retourner"""
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    w = data.get("weights", {})
    merged = dict(DEFAULT_WEIGHTS)
    for k, v in w.items():
        if k in merged:
            merged[k] = float(v)
    return clamp_weights(merged)


def get_best_weights() -> Dict[str, float]:
    """Charge et retourne les meilleurs poids actuels en lisant best.json pour trouver le chemin du fichier,
      puis en chargeant ce fichier avec load_gen. Si le fichier pointé n'existe plus, replie sur gen_0"""
    
    ensure_defaults()
    with open(best_path(), "r", encoding="utf-8") as f:
        data = json.load(f)
    p = data.get("path")
    if not p or not os.path.exists(p):
        p = gen_path(0)
        set_best(p)
    return load_gen(p)


def get_best_file() -> str:
    """Retourne simplement le chemin du meilleur fichier de poids actuel (sans charger son contenu)"""
    ensure_defaults()
    with open(best_path(), "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("path") or gen_path(0)


def set_best(weights_file: str) -> None:
    """Écrit dans best.json le chemin absolu du nouveau meilleur fichier de poids
      Appelée après chaque candidat accepté pour mettre à jour le pointeur"""
    
    with open(best_path(), "w", encoding="utf-8") as f:
        json.dump({"path": os.path.abspath(weights_file)}, f, indent=2)


def latest_generation_index() -> int:
    """ Parcourt les fichiers weights_gen_0.json, weights_gen_1.json, etc 
    en incrémentant jusqu'à ne plus en trouver. Retourne le numéro de la génération la plus récente"""
    ensure_defaults()
    i = 0
    while os.path.exists(gen_path(i + 1)):
        i += 1
    return i