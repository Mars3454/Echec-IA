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
from chess_ai.var import *

variable = Variable()

DEPTH = 3
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
OPENING_BOOK = {
    "e2e4": ["c7c5", "e7e5", "e7e6"],
    "d2d4": ["d7d5", "g8f6"],
    "g1f3": ["d7d5", "g8f6"],
    "c2c4": ["e7e5", "c7c5"],
}


# ==================== RÉSULTAT ====================

@dataclass
class SearchResult:
    """Résultat de recherche, compatible avec les deux GUIs."""
    move: Optional[chess.Move]
    score: float
    nodes: int


# ==================== HEURISTIQUE ====================

def heuristic_move_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            score += PIECE_VALUES[captured.piece_type] * 10
    if board.gives_check(move):
        score += 5
    if move.promotion:
        score += PIECE_VALUES.get(move.promotion, 0) * 10
    return score


# ==================== MINIMAX + ALPHA-BETA ====================

def minimax(board: chess.Board, depth: int, alpha: float, beta: float,
            maximizing: bool, nodes_ref: list) -> tuple:
    """
    Minimax avec élagage alpha-bêta.
    nodes_ref = [0]  — compteur de nœuds passé par référence.
    Retourne (score, best_move).
    """
    nodes_ref[0] += 1

    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    moves = list(board.legal_moves)
    moves.sort(key=lambda m: heuristic_move_score(board, m), reverse=True)

    best_move = None

    if maximizing:          # IA (NOIRS)
        best_val = -float("inf")
        for move in moves:
            board.push(move)
            val, _ = minimax(board, depth - 1, alpha, beta, False, nodes_ref)
            board.pop()
            if val > best_val:
                best_val = val
                best_move = move
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best_val, best_move

    else:                   # Joueur (BLANCS)
        best_val = float("inf")
        for move in moves:
            board.push(move)
            val, _ = minimax(board, depth - 1, alpha, beta, True, nodes_ref)
            board.pop()
            if val < best_val:
                best_val = val
                best_move = move
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best_val, best_move


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
    score, move = minimax(board, depth, alpha, beta, maximizing, nodes_ref)
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
    if board.fullmove_number <= 3 and len(board.move_stack) > 0:
        last = board.move_stack[-1].uci()
        if last in OPENING_BOOK:
            import random
            return chess.Move.from_uci(random.choice(OPENING_BOOK[last]))

    nodes_ref = [0]
    maximizing = (board.turn == chess.BLACK)
    _, move = minimax(board, DEPTH, -float("inf"), float("inf"), maximizing, nodes_ref)
    return move


# ==================== CHOOSE_BEST_MOVE (pour gui.py) ====================

def choose_best_move(board: chess.Board, depth: int,
                     weights: Any = None) -> SearchResult:
    """
    Interface attendue par gui.py.
    Joue le meilleur coup à la profondeur donnée.
    """
    # Livre d'ouverture
    if board.fullmove_number <= 3 and len(board.move_stack) > 0:
        last = board.move_stack[-1].uci()
        if last in OPENING_BOOK:
            import random
            uci = random.choice(OPENING_BOOK[last])
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                return SearchResult(move=move, score=evaluate_board(board), nodes=1)

    nodes_ref = [0]
    maximizing = (board.turn == chess.BLACK)
    score, move = minimax(board, depth, -float("inf"), float("inf"),
                          maximizing, nodes_ref)
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

    for depth in range(1, max_depth + 1):
        if (time.time() - start) * 1000 >= movetime_ms:
            break
        nodes_ref = [0]
        score, move = minimax(board, depth, -float("inf"), float("inf"),
                              maximizing, nodes_ref)
        nodes_total += nodes_ref[0]
        if move is not None:
            best_move = move
            best_score = score

    return SearchResult(move=best_move, score=best_score, nodes=nodes_total)