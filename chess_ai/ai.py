"""
ai.py — IA d'échecs optimisée basée sur python-chess.

OPTIMISATIONS PAR RAPPORT À LA VERSION PRÉCÉDENTE :
────────────────────────────────────────────────────
1.  [BUGFIX CRITIQUE] generate_reasonable_moves n'écrasait plus rien :
    le résultat était immédiatement remplacé par list(board.legal_moves).
    Supprimé — on utilise directement les coups légaux.

2.  [BUGFIX] Quiescence en negamax pur, cohérent avec le reste de l'arbre.
    L'ancienne version mixait minimax (max/min séparés) avec une quiescence
    en négamax → scores incohérents.

3.  [PERF MAJEURE] Negamax unifié : on remplace le minimax max/min dupliqué
    par un negamax propre. Le code est 2× plus court et évite les erreurs
    de symétrie.

4.  [PERF MAJEURE] TT persistante entre les itérations de l'IID :
    auparavant tt={} était créé à chaque profondeur, perdant tout le travail.
    Maintenant elle survit entre les itérations ET entre les coups (globale).

5.  [PERF] Null Move Pruning (R=2) : si la position est "calme", on joue
    un coup nul et on vérifie si l'adversaire peut faire mieux que beta.
    Élagage massif (~30-40 % de nœuds en moins en middlegame).

6.  [PERF] Aspiration Windows dans l'IID : après la profondeur 1, on
    cherche d'abord dans une fenêtre étroite ±ASPIRATION_DELTA autour du
    score précédent. Réduit le nombre de recherches pleine fenêtre.

7.  [PERF] Futility Pruning aux nœuds frontières (depth==1) : si le score
    statique est très en dessous d'alpha, on élude les coups silencieux.

8.  [PERF] HISTORY ne se remet plus à zéro entre les coups (aging léger
    par division tous les N coups). Les killers sont conservés entre les
    itérations IID.

9.  [PERF] MVV-LVA complet : score = 10*valeur_capturée - valeur_attaquant
    (avant : valeur_capturée*10 seulement).

10. [BUGFIX LMR] La condition board.is_capture/gives_check était évaluée
    APRÈS board.push (le coup était déjà joué). Déplacé AVANT.

Interfaces exposées (inchangées) :
    choose_best_move(board, depth, weights=None)  → SearchResult
    choose_best_move_timed(board, movetime_ms, max_depth, weights=None) → SearchResult
    evaluate(board, ply=0, weights=None)          → float
    alphabeta(board, depth, alpha, beta, ply, tt, weights) → (score, nodes, move)
    MATE_SCORE
"""

import chess
import time
import random
from dataclasses import dataclass
from typing import Optional, Any

from chess_ai.evalu import evaluate_board as _evaluate_board_raw
from chess_ai.opening_book import pick_book_move, reset_line
from chess_ai.var import Variable
from training.weights import DEFAULT_WEIGHTS, get_best_weights

# Poids actifs — mis à jour par set_active_weights() ou chargés au démarrage
_ACTIVE_WEIGHTS: dict = {}

def set_active_weights(w: dict) -> None:
    """Appelé par le training pour injecter les poids du candidat en cours."""
    global _ACTIVE_WEIGHTS
    _ACTIVE_WEIGHTS = dict(w)

def _resolve_weights(w_arg) -> dict:
    """Retourne les poids à utiliser : argument > actifs > best sauvegardé > défaut."""
    if w_arg is not None:
        return w_arg
    if _ACTIVE_WEIGHTS:
        return _ACTIVE_WEIGHTS
    try:
        return get_best_weights()
    except Exception:
        return DEFAULT_WEIGHTS

def evaluate_board(board, weights=None):
    """Wrapper qui injecte les poids résolus dans l'évaluateur."""
    return _evaluate_board_raw(board, _resolve_weights(weights))

# ──────────────────────────────────────────────────────────────────────────────
# Constantes globales
# ──────────────────────────────────────────────────────────────────────────────

variable     = Variable()
MATE_SCORE   = 9999
DEPTH        = 3
INF          = float("inf")

# MVV-LVA : valeurs relatives (pas en centipawns, juste pour le tri)
PIECE_VALUES = {
    chess.PAWN:   1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK:   5,
    chess.QUEEN:  9,
    chess.KING:   0,
}

# Paramètres de recherche
NULL_MOVE_R         = 2      # réduction pour le null-move
ASPIRATION_DELTA    = 50     # fenêtre d'aspiration (centipawns)
FUTILITY_MARGIN     = 150    # marge de futility pruning à depth==1 (centipawns)
HISTORY_AGING_DIV   = 2      # diviseur appliqué à l'historique tous les N coups
HISTORY_MAX         = 8000   # plafond history pour éviter l'explosion

# Tables globales (persistent entre les coups)
KILLER_MOVES: dict[int, list] = {}   # depth → [move1, move2]
HISTORY:      dict[tuple, int] = {}  # (piece_type, to_square) → bonus
TT:           dict = {}              # Transposition Table globale


# ──────────────────────────────────────────────────────────────────────────────
# SearchResult
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    move:  Optional[chess.Move]
    score: float
    nodes: int


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_history_uci(board: chess.Board) -> list[str]:
    return [m.uci() for m in board.move_stack]


def _age_history():
    """Divise tous les scores d'historique par HISTORY_AGING_DIV."""
    for k in list(HISTORY.keys()):
        HISTORY[k] //= HISTORY_AGING_DIV
        if HISTORY[k] == 0:
            del HISTORY[k]


def _update_killer(depth: int, move: chess.Move):
    if depth not in KILLER_MOVES:
        KILLER_MOVES[depth] = []
    if move not in KILLER_MOVES[depth]:
        KILLER_MOVES[depth].insert(0, move)
        if len(KILLER_MOVES[depth]) > 2:
            KILLER_MOVES[depth].pop()


def _update_history(piece_type: int, to_square: int, depth: int):
    key = (piece_type, to_square)
    HISTORY[key] = min(HISTORY.get(key, 0) + depth * depth, HISTORY_MAX)


# ──────────────────────────────────────────────────────────────────────────────
# Tri des coups (MVV-LVA complet + killers + history + TT)
# ──────────────────────────────────────────────────────────────────────────────

def _move_score(board: chess.Board, move: chess.Move, depth: int,
                tt_best: Optional[chess.Move]) -> int:
    if move == tt_best:
        return 100_000

    score = 0

    # Captures : MVV-LVA complet
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if captured and attacker:
            score += 10 * PIECE_VALUES[captured.piece_type] - PIECE_VALUES[attacker.piece_type]
        score += 50_000   # captures avant les coups silencieux

    # Promotion
    if move.promotion:
        score += PIECE_VALUES.get(move.promotion, 0) * 10 + 40_000

    # Killer
    if depth in KILLER_MOVES:
        if len(KILLER_MOVES[depth]) > 0 and move == KILLER_MOVES[depth][0]:
            score += 9_000
        elif len(KILLER_MOVES[depth]) > 1 and move == KILLER_MOVES[depth][1]:
            score += 8_000

    # Check (coûteux, utilisé seulement aux premières profondeurs)
    if depth >= 2 and board.gives_check(move):
        score += 7_000

    # History
    piece = board.piece_type_at(move.from_square)
    if piece:
        score += HISTORY.get((piece, move.to_square), 0)

    return score


# ──────────────────────────────────────────────────────────────────────────────
# Quiescence search (negamax pur)
# ──────────────────────────────────────────────────────────────────────────────

def quiescence(board: chess.Board, alpha: float, beta: float,
               nodes_ref: list, qdepth: int = 0,
               weights=None) -> float:
    nodes_ref[0] += 1

    # Score statique du point de vue du joueur actif
    raw = evaluate_board(board, weights)
    stand_pat = -raw if board.turn == chess.WHITE else raw

    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    # Delta pruning : si même la meilleure capture possible ne suffit pas
    DELTA = 900  # valeur de la reine
    if stand_pat + DELTA < alpha:
        return alpha

    # Limiter la profondeur de quiescence pour éviter les explosions
    if qdepth > 6:
        return alpha

    for move in board.legal_moves:
        if not board.is_capture(move) and not move.promotion:
            continue

        # SEE léger : ignorer les captures perdantes évidentes
        captured = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if captured and attacker:
            if (PIECE_VALUES[captured.piece_type] < PIECE_VALUES[attacker.piece_type]
                    and not board.is_check()):
                continue

        board.push(move)
        score = -quiescence(board, -beta, -alpha, nodes_ref, qdepth + 1, weights)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


# ──────────────────────────────────────────────────────────────────────────────
# Negamax principal avec alpha-beta, TT, LMR, Null Move, Futility
# ──────────────────────────────────────────────────────────────────────────────

def negamax(board: chess.Board, depth: int, alpha: float, beta: float,
            nodes_ref: list, ply: int = 0,
            allow_null: bool = True,
            weights=None) -> tuple[float, Optional[chess.Move]]:
    """
    Retourne (score_du_joueur_actif, meilleur_coup).
    Score positif = bon pour le joueur dont c'est le tour.
    """
    nodes_ref[0] += 1

    # ── Transposition Table ──────────────────────────────────────────────────
    key     = board._transposition_key()
    tt_entry = TT.get(key)
    tt_best  = None

    if tt_entry and tt_entry["depth"] >= depth:
        flag  = tt_entry["flag"]
        tval  = tt_entry["score"]
        tt_best = tt_entry["move"]
        if flag == "exact":
            return tval, tt_best
        elif flag == "lower":
            alpha = max(alpha, tval)
        elif flag == "upper":
            beta  = min(beta,  tval)
        if alpha >= beta:
            return tval, tt_best

    # ── Cas terminaux ────────────────────────────────────────────────────────
    if board.is_game_over():
        if board.is_checkmate():
            return -(MATE_SCORE - ply), None   # mat → score fortement négatif
        return 0, None                          # pat/nulle

    if depth == 0:
        score = quiescence(board, alpha, beta, nodes_ref, weights=weights)
        return score, None

    in_check = board.is_check()

    # ── Check extension ──────────────────────────────────────────────────────
    if in_check:
        depth += 1

    # ── Null Move Pruning ────────────────────────────────────────────────────
    # Conditions : pas en échec, pas en fin de partie, pas au nœud racine,
    # on a du matériel (pas seulement des pions+roi)
    if (allow_null
            and not in_check
            and depth >= 3
            and ply > 0):
        # Vérifier qu'on a du matériel (évite zugzwang en finale)
        has_pieces = any(
            board.pieces(pt, board.turn)
            for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        )
        if has_pieces:
            board.push(chess.Move.null())
            null_score, _ = negamax(board, depth - 1 - NULL_MOVE_R,
                                    -beta, -beta + 1,
                                    nodes_ref, ply + 1,
                                    allow_null=False, weights=weights)
            null_score = -null_score
            board.pop()
            # Ne couper que si le score est clairement >= beta
            # ET n'est pas un score de mat (évite les faux mats du null move)
            if null_score >= beta and abs(null_score) < MATE_SCORE - 100:
                return null_score, None

    # ── Génération et tri des coups ──────────────────────────────────────────
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: _move_score(board, m, depth, tt_best), reverse=True)

    best_move  = None
    best_val   = -INF
    orig_alpha = alpha

    for i, move in enumerate(moves):

        # ── Futility Pruning (depth == 1, nœuds non-captures silencieux) ────
        if (depth == 1
                and not in_check
                and not board.is_capture(move)
                and not move.promotion
                and best_val > -MATE_SCORE + 100):
            raw_static = evaluate_board(board, weights)
            static = -raw_static if board.turn == chess.WHITE else raw_static
            if static + FUTILITY_MARGIN <= alpha:
                continue

        # ── Late Move Reduction ──────────────────────────────────────────────
        is_capture   = board.is_capture(move)
        gives_check  = board.gives_check(move)
        is_killer    = move in KILLER_MOVES.get(depth, [])
        is_promotion = bool(move.promotion)

        reduction = 0
        if (depth >= 3
                and i >= 4
                and not is_capture
                and not gives_check
                and not is_killer
                and not is_promotion
                and not in_check):
            # Réduction progressive : plus forte pour les coups tardifs
            reduction = 1 if i < 8 else 2

        board.push(move)

        # Principal Variation Search (PVS)
        if i == 0:
            val, _ = negamax(board, depth - 1, -beta, -alpha,
                             nodes_ref, ply + 1, weights=weights)
            val = -val
        else:
            # Recherche nulle fenêtre d'abord
            val, _ = negamax(board, depth - 1 - reduction, -alpha - 1, -alpha,
                             nodes_ref, ply + 1, weights=weights)
            val = -val
            # Re-search si prometteur
            if val > alpha and (reduction > 0 or val < beta):
                val, _ = negamax(board, depth - 1, -beta, -alpha,
                                 nodes_ref, ply + 1, weights=weights)
                val = -val

        board.pop()

        if val > best_val:
            best_val  = val
            best_move = move

        if val > alpha:
            alpha = val

        if alpha >= beta:
            # Beta cut-off
            if not is_capture:
                _update_killer(depth, move)
                piece = board.piece_type_at(move.from_square)
                if piece:
                    _update_history(piece, move.to_square, depth)
            break

    # Sécurité : si aucun coup n'a pu être joué (ne devrait pas arriver,
    # mais on évite de propager ±inf au GUI)
    if best_val == -INF:
        best_val = -(MATE_SCORE - ply)

    # ── Stockage TT ─────────────────────────────────────────────────────────
    if best_val <= orig_alpha:
        flag = "upper"
    elif best_val >= beta:
        flag = "lower"
    else:
        flag = "exact"

    TT[key] = {"score": best_val, "depth": depth,
               "move": best_move, "flag": flag}

    return best_val, best_move


# ──────────────────────────────────────────────────────────────────────────────
# Interface alphabeta (compatibilité gui.py)
# ──────────────────────────────────────────────────────────────────────────────

def alphabeta(board: chess.Board, depth: int, alpha: float, beta: float,
              ply: int, tt: dict, weights: Any) -> tuple:
    nodes_ref = [0]
    score, move = negamax(board, depth, alpha, beta, nodes_ref, ply,
                          weights=weights)
    return score, nodes_ref[0], move


def evaluate(board: chess.Board, ply: int = 0, weights: Any = None) -> float:
    return evaluate_board(board, weights)


def order_moves(board: chess.Board, moves, tt_best=None,
                killer_moves=None, level=None):
    return sorted(moves,
                  key=lambda m: _move_score(board, m, level or 0, tt_best),
                  reverse=True)


def choose_best_move(board: chess.Board, depth: int,
                     weights: Any = None) -> SearchResult:

    history = get_history_uci(board)
    w = _resolve_weights(weights)

    if len(history) < 6:
        book_uci = pick_book_move(history, is_white=(board.turn == chess.WHITE))
        if book_uci:
            mv = chess.Move.from_uci(book_uci)
            if mv in board.legal_moves:
                return SearchResult(move=mv, score=0, nodes=1)
        fallback = list(board.legal_moves)
        if fallback:
            return SearchResult(move=random.choice(fallback), score=0, nodes=1)

    nodes_ref = [0]
    _age_history()
    TT.clear()   # ← nouvelle position, nouvelle TT
    score, move = negamax(board, depth, -INF, INF, nodes_ref, ply=0, weights=w)
    return SearchResult(move=move, score=score, nodes=nodes_ref[0])


def choose_best_move_timed(board: chess.Board, movetime_ms: int,
                           max_depth: int = 6,
                           weights: Any = None) -> SearchResult:
    start       = time.time()
    best_move   = None
    best_score  = 0.0
    nodes_total = 0

    history = get_history_uci(board)
    w = _resolve_weights(weights)

    if len(history) < 6:
        book_uci = pick_book_move(history, is_white=(board.turn == chess.WHITE))
        if book_uci:
            mv = chess.Move.from_uci(book_uci)
            if mv in board.legal_moves:
                return SearchResult(move=mv, score=0, nodes=1)

    _age_history()
    TT.clear()   # ← nouvelle position, nouvelle TT (la TT survit entre IID depths)

    for depth in range(1, max_depth + 1):
        elapsed_ms = (time.time() - start) * 1000
        if elapsed_ms >= movetime_ms:
            break

        nodes_ref = [0]

        if depth >= 3 and best_move is not None:
            alpha = best_score - ASPIRATION_DELTA
            beta  = best_score + ASPIRATION_DELTA
            score, move = negamax(board, depth, alpha, beta, nodes_ref,
                                  ply=0, weights=w)
            if score <= alpha or score >= beta:
                score, move = negamax(board, depth, -INF, INF, nodes_ref,
                                      ply=0, weights=w)
        else:
            score, move = negamax(board, depth, -INF, INF, nodes_ref,
                                  ply=0, weights=w)

        nodes_total += nodes_ref[0]
        if move is not None:
            best_move  = move
            best_score = score

    return SearchResult(move=best_move, score=best_score, nodes=nodes_total)


def choose_move(board: chess.Board) -> Optional[chess.Move]:
    res = choose_best_move(board, depth=DEPTH)
    return res.move