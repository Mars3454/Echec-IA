"""
engine_chess.py — Couche d'adaptation python-chess ↔ GUI existant.

Remplace engine.py en exposant exactement les mêmes noms/signatures
que l'ancien engine.py, mais en s'appuyant sur python-chess en coulisse.

Interfaces exposées (identiques à l'ancien engine.py) :
    GameState
    initial_board()
    piece_symbol(piece)
    legal_moves(state)
    apply_move_inplace(state, move)
    make_move(state, move)
    is_checkmate(state)
    is_stalemate(state)
    in_check(state, color)
    move_to_uci(move)
    uci_to_move(state, uci)
    state_to_fen(state)
    fen_to_state(fen)

    Move  (dataclass compatible)
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING  (constantes)
"""

from __future__ import annotations
import chess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ==================== CONSTANTES (mêmes valeurs qu'avant) ====================

PAWN   = chess.PAWN    # 1
KNIGHT = chess.KNIGHT  # 2
BISHOP = chess.BISHOP  # 3
ROOK   = chess.ROOK    # 4
QUEEN  = chess.QUEEN   # 5
KING   = chess.KING    # 6

# ==================== SYMBOLES UNICODE ====================

_SYMBOLS = {
    None: " ",
    # Blancs
    (chess.PAWN,   chess.WHITE): "♙",
    (chess.KNIGHT, chess.WHITE): "♘",
    (chess.BISHOP, chess.WHITE): "♗",
    (chess.ROOK,   chess.WHITE): "♖",
    (chess.QUEEN,  chess.WHITE): "♕",
    (chess.KING,   chess.WHITE): "♔",
    # Noirs
    (chess.PAWN,   chess.BLACK): "♟",
    (chess.KNIGHT, chess.BLACK): "♞",
    (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK,   chess.BLACK): "♜",
    (chess.QUEEN,  chess.BLACK): "♛",
    (chess.KING,   chess.BLACK): "♚",
}

def piece_symbol(piece) -> str:
    """
    Accepte :
      - None / 0      → espace
      - chess.Piece   → symbole unicode
      - int signé     → (ancien engine.py) converti automatiquement
    """
    if piece is None or piece == 0:
        return " "
    if isinstance(piece, chess.Piece):
        return _SYMBOLS.get((piece.piece_type, piece.color), " ")
    # entier signé (ancienne convention) : positif = blanc, négatif = noir
    if isinstance(piece, int):
        color = chess.WHITE if piece > 0 else chess.BLACK
        ptype = abs(piece)
        return _SYMBOLS.get((ptype, color), " ")
    return " "


# ==================== MOVE ====================

@dataclass(frozen=True)
class Move:
    """
    Enveloppe chess.Move pour compatibilité avec le GUI.
    Le GUI utilise : move.sr, .sc, .er, .ec, .promotion, .is_en_passant, .is_castling
    """
    sr: int
    sc: int
    er: int
    ec: int
    promotion: Optional[int] = None
    is_en_passant: bool = False
    is_castling: bool = False
    _chess_move: Optional[chess.Move] = field(default=None, compare=False, hash=False)

    @staticmethod
    def from_chess(cm: chess.Move, board: chess.Board) -> "Move":
        """Construit un Move depuis un chess.Move en lisant le plateau."""
        sr = 7 - chess.square_rank(cm.from_square)
        sc = chess.square_file(cm.from_square)
        er = 7 - chess.square_rank(cm.to_square)
        ec = chess.square_file(cm.to_square)

        is_ep = board.is_en_passant(cm)
        is_castling = board.is_castling(cm)
        promo = cm.promotion  # None ou int chess

        return Move(sr=sr, sc=sc, er=er, ec=ec,
                    promotion=promo,
                    is_en_passant=is_ep,
                    is_castling=is_castling,
                    _chess_move=cm)

    def to_chess(self) -> chess.Move:
        """Retourne le chess.Move sous-jacent."""
        if self._chess_move is not None:
            return self._chess_move
        from_sq = chess.square(self.sc, 7 - self.sr)
        to_sq   = chess.square(self.ec, 7 - self.er)
        return chess.Move(from_sq, to_sq, promotion=self.promotion)


# ==================== GAMESTATE ====================

class GameState:
    """
    Enveloppe chess.Board pour compatibilité avec le GUI existant.

    Le GUI accède à :
        state.board[r][c]      → int signé (>0 blanc, <0 noir, 0 vide)
        state.turn             → 1 (blancs) ou -1 (noirs)
        state.move_history     → list[str] UCI
    """

    def __init__(self, board: Optional[chess.Board] = None, turn: int = 1):
        if board is None:
            self._board = chess.Board()
        elif isinstance(board, list):
            # Cas initial_board() appelé avec une grille — on crée une position vide
            self._board = chess.Board()
        else:
            self._board = board

        # turn est ignoré : on suit chess.Board.turn
        self._move_history: List[str] = []

    # ---- Propriétés compatibles GUI ----

    @property
    def board(self) -> List[List[int]]:
        """Grille 8×8 d'entiers signés (>0 blanc, <0 noir, 0 vide)."""
        grid = [[0] * 8 for _ in range(8)]
        for sq in chess.SQUARES:
            piece = self._board.piece_at(sq)
            if piece:
                r = 7 - chess.square_rank(sq)
                c = chess.square_file(sq)
                sign = 1 if piece.color == chess.WHITE else -1
                grid[r][c] = sign * piece.piece_type
        return grid

    @property
    def turn(self) -> int:
        return 1 if self._board.turn == chess.WHITE else -1

    @turn.setter
    def turn(self, value: int):
        self._board.turn = chess.WHITE if value == 1 else chess.BLACK

    @property
    def move_history(self) -> List[str]:
        return self._move_history

    # ---- Accès au plateau sous-jacent ----

    def get_board(self) -> chess.Board:
        return self._board

    def copy(self) -> "GameState":
        ns = GameState(board=self._board.copy())
        ns._move_history = list(self._move_history)
        return ns

    def king_pos(self, color: int) -> Tuple[int, int]:
        chess_color = chess.WHITE if color == 1 else chess.BLACK
        sq = self._board.king(chess_color)
        if sq is None:
            raise ValueError("Roi introuvable.")
        return (7 - chess.square_rank(sq), chess.square_file(sq))


# ==================== FONCTIONS COMPATIBLES GUI ====================

def initial_board() -> chess.Board:
    """Retourne le plateau initial (chess.Board)."""
    return chess.Board()


def legal_moves(state: GameState) -> List[Move]:
    """Retourne la liste des coups légaux sous forme de Move."""
    b = state.get_board()
    return [Move.from_chess(cm, b) for cm in b.legal_moves]


def apply_move_inplace(state: GameState, move) -> None:
    """
    Applique un coup sur l'état (in-place).
    Accepte un Move (wrapper), un chess.Move ou ignore None (sécurité).
    """
    if move is None:
        # Sécurité absolue : on ne fait rien
        return

    b = state.get_board()

    if isinstance(move, Move):
        cm = move.to_chess()
    elif isinstance(move, chess.Move):
        cm = move
    else:
        raise TypeError(f"Type de coup inconnu : {type(move)}")

    if cm not in b.legal_moves:
        raise ValueError(f"Coup illégal : {cm.uci()}")

    b.push(cm)
    state._move_history.append(cm.uci())


def make_move(state: GameState, move) -> GameState:
    """Retourne un nouvel état après application du coup."""
    ns = state.copy()
    apply_move_inplace(ns, move)
    return ns


def is_checkmate(state: GameState) -> bool:
    return state.get_board().is_checkmate()


def is_stalemate(state: GameState) -> bool:
    return state.get_board().is_stalemate()


def in_check(state: GameState, color: int) -> bool:
    b = state.get_board()
    chess_color = chess.WHITE if color == 1 else chess.BLACK
    return b.is_check() and b.turn == chess_color


def has_legal_moves(state: GameState) -> bool:
    return bool(list(state.get_board().legal_moves))


# ==================== UCI ====================

def move_to_uci(move) -> str:
    """Convertit un Move ou chess.Move en chaîne UCI."""
    if isinstance(move, Move):
        return move.to_chess().uci()
    if isinstance(move, chess.Move):
        return move.uci()
    return str(move)


def uci_to_move(state: GameState, uci: str) -> Move:
    """Convertit une chaîne UCI en Move."""
    uci = uci.strip()
    cm = chess.Move.from_uci(uci)
    b = state.get_board()
    if cm not in b.legal_moves:
        raise ValueError(f"Coup non légal : {uci}")
    return Move.from_chess(cm, b)


# ==================== FEN ====================

def state_to_fen(state: GameState) -> str:
    return state.get_board().fen()


def fen_to_state(fen: str) -> GameState:
    b = chess.Board(fen)
    return GameState(board=b)