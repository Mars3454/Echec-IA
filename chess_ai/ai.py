"""
ai.py — Votre IA d'échecs basée sur python-chess.
Conserve votre logique originale (minimax + alpha-beta + heuristique)
et expose les interfaces attendues par gui.py et training_gui.py.

Interfaces exposées:
    choose_best_move(board, depth, weights=None)  → SearchResult
    choose_best_move_timed(board, movetime_ms, max_depth, weights=None) → SearchResult
    evaluate(board, ply=0, weights=None)          → float   (alias evaluate_board)
    alphabeta(board, depth, alpha, beta, ply, tt, weights) → (score, nodes, move)
    MATE_SCORE
"""

import chess
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

from chess_ai.evalu import *
from chess_ai.opening_book import *
from chess_ai.var import *

variable = Variable()
# Killer moves : 2 par profondeur
KILLER_MOVES = {}

# History heuristic
HISTORY = {}
DEPTH = 5
MATE_SCORE = 9999

# Valeurs pour le tri heuristique (MVV-LVA léger)
PIECE_VALUES = {
    chess.PAWN:   1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK:   5,
    chess.QUEEN:  9,
    chess.KING:   0,
}

# Livre d'ouverture étendu

def get_history_uci(board: chess.Board) -> list[str]:
    return [move.uci() for move in board.move_stack]

# ==================== RÉSULTAT ====================

@dataclass
class SearchResult:
    """Résultat de recherche, compatible avec les deux GUIs."""
    move: Optional[chess.Move]
    score: float
    nodes: int


# ==================== HEURISTIQUE ====================

def heuristic_move_score(board: chess.Board, move: chess.Move, depth: int) -> int:
    score = 0

    # 1️⃣ Captures MVV-LVA léger
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            score += PIECE_VALUES[captured.piece_type] * 10

    # 2️⃣ Promotion
    if move.promotion:
        score += PIECE_VALUES.get(move.promotion, 0) * 10

    # 3️⃣ Check
    if board.gives_check(move):
        score += 5

    # 4️⃣ Killer move bonus
    if depth in KILLER_MOVES and move in KILLER_MOVES[depth]:
        score += 5000

    # 5️⃣ History heuristic bonus
    key = (board.piece_type_at(move.from_square), move.to_square)
    score += HISTORY.get(key, 0)

    return score



# ==================== MINIMAX + ALPHA-BETA ====================
def generate_reasonable_moves(board):
    moves = []
    for m in board.legal_moves:
        if board.is_capture(m):
            moves.append(m)
        elif board.gives_check(m):
            moves.append(m)
        elif board.piece_type_at(m.from_square) in (chess.KNIGHT, chess.BISHOP):
            moves.append(m)
        elif chess.square_rank(m.to_square) in (3, 4):  # centre
            moves.append(m)
    return moves

def minimax(board: chess.Board, depth: int, alpha: float, beta: float,
            maximizing: bool, nodes_ref: list, tt: dict) -> tuple:
    moves = generate_reasonable_moves(board)
    if not moves:
        moves = list(board.legal_moves)
    
    nodes_ref[0] += 1

    key = board._transposition_key()    # Transposition Table
    if key in tt and tt[key]["depth"] >= depth:
        return tt[key]["score"], tt[key]["move"]

    if depth == 0:
        score = quiescence(board, alpha, beta, nodes_ref)
        return score, None

    if board.is_game_over():
        return evaluate_board(board), None

    moves = list(board.legal_moves)

    # Move ordering amélioré
    tt_best = tt[key]["move"] if key in tt else None
    moves.sort(
        key=lambda m: heuristic_move_score(board, m, depth)
                      + (10000 if m == tt_best else 0),
        reverse=True
    )

    best_move = None

    if maximizing:
        best_val = -float("inf")

        for i, move in enumerate(moves):

            board.push(move)

            reduction = 0

            # 🔥 Late Move Reduction
            if (
                depth >= 3
                and i >= 3  # pas les 3 premiers coups
                and not board.is_capture(move)
                and not board.gives_check(move)
                and move not in KILLER_MOVES.get(depth, [])
            ):
                reduction = 1

            val, _ = minimax(
                board,
                depth - 1 - reduction,
                alpha,
                beta,
                False,
                nodes_ref,
                tt
            )

            # Si coup réduit semble intéressant → re-search complet
            if reduction and val > alpha:
                val, _ = minimax(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                    False,
                    nodes_ref,
                    tt
                )

            board.pop()

            if val > best_val:
                best_val = val
                best_move = move

            alpha = max(alpha, val)

            if beta <= alpha:

                # Killer moves
                if not board.is_capture(move):
                    if depth not in KILLER_MOVES:
                        KILLER_MOVES[depth] = []
                    if move not in KILLER_MOVES[depth]:
                        KILLER_MOVES[depth].append(move)
                        if len(KILLER_MOVES[depth]) > 2:
                            KILLER_MOVES[depth].pop(0)

                # History
                hkey = (board.piece_type_at(move.from_square), move.to_square)
                HISTORY[hkey] = HISTORY.get(hkey, 0) + depth * depth

                break

    else:
        best_val = float("inf")

        for i, move in enumerate(moves):

            board.push(move)

            reduction = 0

            # 🔥 Late Move Reduction
            if (
                depth >= 3
                and i >= 3
                and not board.is_capture(move)
                and not board.gives_check(move)
                and move not in KILLER_MOVES.get(depth, [])
            ):
                reduction = 1

            val, _ = minimax(
                board,
                depth - 1 - reduction,
                alpha,
                beta,
                True,
                nodes_ref,
                tt
            )

            # Re-search si nécessaire
            if reduction and val < beta:
                val, _ = minimax(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                    True,
                    nodes_ref,
                    tt
                )

            board.pop()

            if val < best_val:
                best_val = val
                best_move = move

            beta = min(beta, val)

            if beta <= alpha:

                # Killer moves
                if not board.is_capture(move):
                    if depth not in KILLER_MOVES:
                        KILLER_MOVES[depth] = []
                    if move not in KILLER_MOVES[depth]:
                        KILLER_MOVES[depth].append(move)
                        if len(KILLER_MOVES[depth]) > 2:
                            KILLER_MOVES[depth].pop(0)

                # History
                hkey = (board.piece_type_at(move.from_square), move.to_square)
                HISTORY[hkey] = HISTORY.get(hkey, 0) + depth * depth

                break

    # Stockage TT
    tt[key] = {
        "score": best_val,
        "depth": depth,
        "move": best_move
    }

    return best_val, best_move


# ==================== Quiescence serach (pour minimax) ====================
def good_capture(board, move):
    if not board.is_capture(move):
        return False
    captured = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    if not captured or not attacker:
        return False
    return PIECE_VALUES[captured.piece_type] >= PIECE_VALUES[attacker.piece_type]


def quiescence(board: chess.Board, alpha: float, beta: float, nodes_ref: list):
    
    nodes_ref[0] += 1

    stand_pat = evaluate_board(board)

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    # On ne considère que les captures et promotions
    for move in board.legal_moves:
        if not good_capture(board, move) and not move.promotion:
            continue
        if not (board.is_capture(move) or move.promotion):
            continue

        board.push(move)
        score = -quiescence(board, -beta, -alpha, nodes_ref)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha

# ==================== INTERFACE ALPHABETA (pour gui.py) ====================

def alphabeta(board: chess.Board, depth: int, alpha: float, beta: float,
              ply: int, tt: dict, weights: Any) -> tuple:
    """
    Wrapper autour de minimax pour être compatible avec l'appel du GUI :
        score, nodes, move = alphabeta(child, depth-1, -MATE, MATE, 1, tt, weights)
    Retourne (score, nodes, best_move).
    """
    nodes_ref = [0]
    maximizing = (board.turn == chess.BLACK)
    score, move = minimax(board, depth, alpha, beta, maximizing, nodes_ref,tt)
    return score, nodes_ref[0], move


# ==================== ÉVALUATION (alias pour gui.py) ====================

def evaluate(board: chess.Board, ply: int = 0, weights: Any = None) -> float:
    """Alias de evaluate_board, compatible avec l'appel du GUI."""
    return evaluate_board(board)


# ==================== ORDRE DES COUPS (pour gui.py) ====================

def order_moves(board: chess.Board, moves, tt_best=None, killer_moves=None, level=None):
    """Tri des coups, compatible avec l'appel du GUI."""
    return sorted(moves, key=lambda m: heuristic_move_score(board, m), reverse=True)


# ==================== CHOOSE_MOVE (interface originale) ====================

def choose_move(board: chess.Board) -> Optional[chess.Move]:
    """Interface originale de votre ai.py."""
    # Livre d'ouverture
    history = get_history_uci(board)

    if len(history) <= 5:
        book_move_uci = pick_book_move(history)
        if book_move_uci:
            move = chess.Move.from_uci(book_move_uci)
            if move in board.legal_moves:
                return SearchResult(
                    move=move,
                    score=evaluate_board(board),
                    nodes=1
                )

    nodes_ref = [0]
    maximizing = (board.turn == chess.BLACK)
    _, move = minimax(board, DEPTH, -float("inf"), float("inf"), maximizing, nodes_ref)
    return move


# ==================== CHOOSE_BEST_MOVE (pour gui.py) ====================

def choose_best_move(board: chess.Board, depth: int,
                     weights: Any = None) -> SearchResult:

    history = get_history_uci(board)

    # 🔒 OUVERTURE FORCÉE
    if len(history) < 6:
        book_move_uci = pick_book_move(
            history,
            is_white=(board.turn == chess.WHITE)
        )

        if book_move_uci:
            move = chess.Move.from_uci(book_move_uci)
            if move in board.legal_moves:
                return SearchResult(move=move, score=0, nodes=1)

        # fallback ultra rapide si le livre échoue
        return SearchResult(
            move=random.choice(list(board.legal_moves)),
            score=0,
            nodes=1
        )
    nodes_ref = [0]
    maximizing = (board.turn == chess.BLACK)
    tt = {}
    KILLER_MOVES.clear()
    HISTORY.clear()
    score, move = minimax(board, depth, -float("inf"), float("inf"),
                      maximizing, nodes_ref, tt)
    
    return SearchResult(move=move, score=score, nodes=nodes_ref[0])


# ==================== CHOOSE_BEST_MOVE_TIMED (pour training_gui.py) ====================

def choose_best_move_timed(board: chess.Board, movetime_ms: int,
                           max_depth: int = 6, weights: Any = None) -> SearchResult:
    """
    Iterative deepening avec limite de temps.
    Interface attendue par training_gui.py.
    """
    start = time.time()
    best_move = None
    best_score = 0.0
    nodes_total = 0
    maximizing = (board.turn == chess.BLACK)
    tt = {}
    KILLER_MOVES.clear()
    HISTORY.clear()
    history = get_history_uci(board)

    if len(history) < 6:
        book_move_uci = pick_book_move(
            history,
            is_white=(board.turn == chess.WHITE)
        )
        if book_move_uci:
            move = chess.Move.from_uci(book_move_uci)
            if move in board.legal_moves:
                return SearchResult(move=move, score=0, nodes=1)
            

    for depth in range(1, max_depth + 1):
        if (time.time() - start) * 1000 >= movetime_ms:
            break
        nodes_ref = [0]
        score, move = minimax(board, depth, -float("inf"), float("inf"),
                      maximizing, nodes_ref, tt)
        nodes_total += nodes_ref[0]
        if move is not None:
            best_move = move
            best_score = score
    
    return SearchResult(move=best_move, score=best_score, nodes=nodes_total)