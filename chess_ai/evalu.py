"""
commentaire général du fichier : 
Le fichier evalu.py contient la fonction d’évaluation du moteur
Son rôle est d’attribuer un score à une position d’échecs
Convention importante :
Score positif = avantage pour les NOIRS
L’évaluation dépend de plusieurs critères :
-	Matériel
-	Contrôle du centre
-	Développement
-	Sécurité du roi
-	Mobilité
-	Structure des pions
-	Activité du roi en finale
Toutes les valeurs numériques proviennent d’un dictionnaire weights, ce qui permet d’entraîner le moteur

variables : 

-	CENTER_MAIN : cases centrales principales.
-	CENTER_EXT : cases du centre élargi.
-	_PIECE_VALUES_CACHE : cache pour stocker les valeurs des pièces déjà construites.

"""

import chess
from typing import Optional, Dict

# Import des défauts (fallback si weights=None)
from training.weights import DEFAULT_WEIGHTS

# Cases du centre
CENTER_MAIN = [chess.D4, chess.E4, chess.D5, chess.E5]
CENTER_EXT  = [chess.C3, chess.D3, chess.E3, chess.F3,
               chess.C4,                     chess.F4,
               chess.C5,                     chess.F5,
               chess.C6, chess.D6, chess.E6, chess.F6]

# Cache léger pour éviter de reconstruire PIECE_VALUES à chaque appel
_PIECE_VALUES_CACHE: Dict[str, dict] = {}


def _get_piece_values(w: Dict[str, float]) -> dict:
    """Construit le dict pièce→valeur depuis les poids
    Utilise un cache pour éviter de le recalculer à chaque appel"""

    key = f"{w['pv_pawn']},{w['pv_knight']},{w['pv_bishop']},{w['pv_rook']},{w['pv_queen']}"
    if key not in _PIECE_VALUES_CACHE:
        _PIECE_VALUES_CACHE[key] = {
            chess.PAWN:   w["pv_pawn"],
            chess.KNIGHT: w["pv_knight"],
            chess.BISHOP: w["pv_bishop"],
            chess.ROOK:   w["pv_rook"],
            chess.QUEEN:  w["pv_queen"],
            chess.KING:   0.0,
        }
    return _PIECE_VALUES_CACHE[key]


# ──────────────────────────────────────────────────────────────────────────────
# Phase de jeu
# ──────────────────────────────────────────────────────────────────────────────

def game_phase(board: chess.Board, w: Dict[str, float]) -> str:
    """Détermine la phase de la partie :
-	opening (ouverture)
-	middlegame (milieu de jeu)
-	endgame (finale)
Elle se base sur le matériel restant
"""
    material = 0
    for p in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        material += len(board.pieces(p, chess.WHITE))
        material += len(board.pieces(p, chess.BLACK))
    if material > w["phase_opening_threshold"]:
        return "opening"
    elif material > w["phase_endgame_threshold"]:
        return "middlegame"
    else:
        return "endgame"


# ──────────────────────────────────────────────────────────────────────────────
# Sous-fonctions heuristiques
# ──────────────────────────────────────────────────────────────────────────────

def _material_score(board: chess.Board, pv: dict) -> float:
    """Calcule la différence de matériel :
score = matériel_noir - matériel_blanc
"""
    black = sum(len(board.pieces(p, chess.BLACK)) * pv[p] for p in pv)
    white = sum(len(board.pieces(p, chess.WHITE)) * pv[p] for p in pv)
    return black - white


def _center_score(board: chess.Board, w: Dict[str, float]) -> float:
    """Évalue le contrôle du centre :
            -	Centre principal (D4, E4, D5, E5)
            -	Centre élargi
"""
    main_black = sum(board.is_attacked_by(chess.BLACK, sq) for sq in CENTER_MAIN)
    main_white = sum(board.is_attacked_by(chess.WHITE, sq) for sq in CENTER_MAIN)
    ext_black  = sum(board.is_attacked_by(chess.BLACK, sq) for sq in CENTER_EXT)
    ext_white  = sum(board.is_attacked_by(chess.WHITE, sq) for sq in CENTER_EXT)
    return (w["center_attack_bonus"] * (main_black - main_white)
            + w["center_ext_bonus"]  * (ext_black  - ext_white))


def _development_score(board: chess.Board, w: Dict[str, float]) -> float:
    """Mesure le développement des pièces mineures
       Compte les cavaliers et fous qui ont quitté leur rangée initiale
"""

    def developed(color):
        """ Nombre de pièces mineures développées (pas sur la rangée de départ)"""
        count = 0
        back_rank = 0 if color == chess.WHITE else 7
        for pt in [chess.KNIGHT, chess.BISHOP]:
            for sq in board.pieces(pt, color):
                if chess.square_rank(sq) != back_rank:
                    count += 1
        return count
    return float(developed(chess.BLACK) - developed(chess.WHITE))


def _king_safety_score(board: chess.Board, w: Dict[str, float]) -> float:
    """Évalue la sécurité du roi :
                -	Cases attaquées autour du roi
                -	Bonus si le roque est encore possible
"""
    def safety(color):
        """La fonction safety évalue la sécurité du roi pour une couleur donnée
          Elle mesure à quel point le roi est protégé ou exposé dans la position"""

        king = board.king(color)
        if king is None:
            return -5.0
        s = 0.0
        for sq in board.attacks(king):
            if board.is_attacked_by(not color, sq):
                s -= w["ks_attack_penalty"]
        if board.has_castling_rights(color):
            s += w["ks_castling_bonus"]
        return s
    return safety(chess.BLACK) - safety(chess.WHITE)


def _mobility_score(board: chess.Board, w: Dict[str, float]) -> float:
    """Compare le nombre de coups légaux disponibles pour chaque camp.
        Plus un joueur a de mobilité, plus sa position est dynamique.
        """
    saved_turn = board.turn

    board.turn = chess.BLACK
    black_moves = board.legal_moves.count()

    board.turn = chess.WHITE
    white_moves = board.legal_moves.count()

    board.turn = saved_turn
    return w["mobility_factor"] * (black_moves - white_moves)


def _pawn_structure_score(board: chess.Board, w: Dict[str, float]) -> float:
    """Analyse la structure des pions :
                        -	Pions doublés (pénalité)
                        -	Pions isolés (pénalité)
                        -	Pions passés (bonus)
                        -	Avancement des pions passés
"""
    def score_for(color):
        """La fonction score_for sert à évaluer la structure des pions pour une couleur donnée (blanc ou noir)
          Elle analyse plusieurs éléments stratégiques importants"""
        s = 0.0
        pawns = board.pieces(chess.PAWN, color)
        opp   = not color
        direction = 1 if color == chess.WHITE else -1

        for file in range(8):
            pawns_in_file = [p for p in pawns if chess.square_file(p) == file]

            # Doublés
            if len(pawns_in_file) > 1:
                s -= w["pawn_doubled_penalty"] * (len(pawns_in_file) - 1)

            for p in pawns_in_file:
                rank = chess.square_rank(p)

                # Passé : aucun pion adverse devant (colonne + adjacentes)
                passed = True
                for f in [file - 1, file, file + 1]:
                    if not (0 <= f <= 7):
                        continue
                    r_range = (range(rank + 1, 8) if color == chess.WHITE
                               else range(rank - 1, -1, -1))
                    for r in r_range:
                        if chess.square(f, r) in board.pieces(chess.PAWN, opp):
                            passed = False
                            break
                    if not passed:
                        break
                if passed:
                    # Bonus proportionnel à l'avancement
                    advancement = (rank if color == chess.WHITE else 7 - rank)
                    s += w["pawn_passed_bonus"] * (1 + advancement * 0.1)

                # Isolé
                isolated = True
                for af in [file - 1, file + 1]:
                    if 0 <= af <= 7:
                        if any(chess.square_file(p2) == af for p2 in pawns):
                            isolated = False
                            break
                if isolated:
                    s -= w["pawn_isolated_penalty"]

        return s

    return score_for(chess.BLACK) - score_for(chess.WHITE)


def _endgame_king_score(board: chess.Board, w: Dict[str, float]) -> float:
    """En finale : évalue l'activité et  la centralisation du roi."""

    def king_score(color):
        king = board.king(color)
        if king is None:
            return 0.0
        # Activité : nombre de cases attaquées
        activity = w["eg_king_activity"] * len(list(board.attacks(king)))
        # Centralisation : distance au centre
        file = chess.square_file(king)
        rank = chess.square_rank(king)
        dist_center = abs(file - 3.5) + abs(rank - 3.5)
        centralization = w["eg_king_centralization"] * (7.0 - dist_center)
        return activity + centralization

    return king_score(chess.BLACK) - king_score(chess.WHITE)


# ──────────────────────────────────────────────────────────────────────────────
# Évaluation principale
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_board(board: chess.Board,
                   weights: Optional[Dict[str, float]] = None) -> float:
    """
    Fonction principale d’évaluation.
    Étapes :
            1.	Vérifie les cas terminaux (mat, pat)
            2.	Détermine la phase
            3.	Sélectionne les multiplicateurs adaptés
            4.	Combine tous les sous-scores
            5.	Retourne le score final

    Score positif = bon pour les NOIRS.
    weights=None → utilise DEFAULT_WEIGHTS.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Cas terminaux
    if board.is_checkmate():
        return 9999.0 if board.turn == chess.WHITE else -9999.0
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0

    w     = weights
    phase = game_phase(board, w)
    pv    = _get_piece_values(w)

    # Sélection des multiplicateurs de phase
    if phase == "opening":
        pm = {
            "material":    w["op_material"],
            "center":      w["op_center"],
            "development": w["op_development"],
            "king_safety": w["op_king_safety"],
            "mobility":    w["op_mobility"],
            "pawns":       w["op_pawns"],
        }
    elif phase == "middlegame":
        pm = {
            "material":    w["mg_material"],
            "center":      w["mg_center"],
            "development": w["mg_development"],
            "king_safety": w["mg_king_safety"],
            "mobility":    w["mg_mobility"],
            "pawns":       w["mg_pawns"],
        }
    else:  # endgame
        pm = {
            "material":    w["eg_material"],
            "center":      w["eg_center"],
            "development": w["eg_development"],
            "king_safety": w["eg_king_safety"],
            "mobility":    w["eg_mobility"],
            "pawns":       w["eg_pawns"],
        }

    score = 0.0

    # Matériel
    score += pm["material"] * _material_score(board, pv)

    # Centre
    score += pm["center"] * _center_score(board, w)

    # Développement (seulement en ouverture et milieu de jeu)
    if phase in ("opening", "middlegame"):
        score += pm["development"] * _development_score(board, w)

    # Sécurité du roi
    score += pm["king_safety"] * _king_safety_score(board, w)

    # Mobilité
    score += pm["mobility"] * _mobility_score(board, w)

    # Structure de pions
    score += pm["pawns"] * _pawn_structure_score(board, w)

    # Échec
    if board.is_check():
        score += w["ks_check_bonus"] if board.turn == chess.BLACK else -w["ks_check_bonus"]

    # Activité du roi en finale
    if phase == "endgame":
        score += _endgame_king_score(board, w)

    return score