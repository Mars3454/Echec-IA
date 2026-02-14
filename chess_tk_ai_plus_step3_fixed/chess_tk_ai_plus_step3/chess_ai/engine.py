"""
engine.py - Moteur d'échecs (règles complètes) avec plateau en entiers.
- Blanc = positif, Noir = négatif, vide = 0
- Gestion: roque, prise en passant, promotion, détection d'échec, coups légaux
- Ajouts: historique des coups (UCI), conversion UCI<->Move, FEN parse/emit
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

# Codes de pièces (valeur absolue)
PAWN   = 1
KNIGHT = 2
BISHOP = 3
ROOK   = 4
QUEEN  = 5
KING   = 6

# Symboles Unicode pour l'affichage (interface)
PIECE_SYMBOLS = {
    0: " ",
    PAWN: "♙",   -PAWN: "♟",
    KNIGHT: "♘", -KNIGHT: "♞",
    BISHOP: "♗", -BISHOP: "♝",
    ROOK: "♖",   -ROOK: "♜",
    QUEEN: "♕",  -QUEEN: "♛",
    KING: "♔",   -KING: "♚",
}

def piece_symbol(piece: int) -> str:
    return PIECE_SYMBOLS.get(piece, " ")

def initial_board() -> List[List[int]]:
    return [
        [-ROOK, -KNIGHT, -BISHOP, -QUEEN, -KING, -BISHOP, -KNIGHT, -ROOK],
        [-PAWN, -PAWN,   -PAWN,   -PAWN,  -PAWN, -PAWN,   -PAWN,   -PAWN],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0],
        [PAWN, PAWN,   PAWN,   PAWN,  PAWN, PAWN,   PAWN,   PAWN],
        [ROOK, KNIGHT, BISHOP, QUEEN, KING, BISHOP, KNIGHT, ROOK],
    ]

@dataclass(frozen=True)
class CastlingRights:
    wk: bool = True  # white king side
    wq: bool = True  # white queen side
    bk: bool = True  # black king side
    bq: bool = True  # black queen side

@dataclass(frozen=True)
class Move:
    """Un coup: (sr, sc) -> (er, ec) avec éventuels flags."""
    sr: int
    sc: int
    er: int
    ec: int
    promotion: Optional[int] = None  # valeur absolue (ex: QUEEN)
    is_en_passant: bool = False
    is_castling: bool = False

@dataclass
class GameState:
    board: List[List[int]]
    turn: int = 1  # 1 = blancs, -1 = noirs
    castling: CastlingRights = CastlingRights()
    en_passant: Optional[Tuple[int,int]] = None  # case capturable (r, c)
    halfmove_clock: int = 0
    fullmove_number: int = 1
    move_history: List[str] = field(default_factory=list)  # coups UCI joués depuis le début

    def copy(self) -> "GameState":
        return GameState(
            board=[row[:] for row in self.board],
            turn=self.turn,
            castling=self.castling,
            en_passant=self.en_passant,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
            move_history=list(self.move_history),
        )

    def king_pos(self, color:int) -> Tuple[int,int]:
        target = KING if color == 1 else -KING
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == target:
                    return (r,c)
        raise ValueError("Roi introuvable (position invalide).")

def in_bounds(r:int,c:int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8

def opponent(color:int) -> int:
    return -color

# --- UCI helpers --------------------------------------------------------------

_FILES = "abcdefgh"
_RANKS = "12345678"

def rc_to_sq(r:int, c:int) -> str:
    """(r,c) -> 'a1'..'h8' (r=7 => rang 1)."""
    return f"{_FILES[c]}{_RANKS[7-r]}"

def sq_to_rc(sq: str) -> Tuple[int,int]:
    """'a1'..'h8' -> (r,c)."""
    file = _FILES.index(sq[0])
    rank = _RANKS.index(sq[1])
    r = 7 - rank
    c = file
    return r, c

_PROMO_MAP = {'q': QUEEN, 'r': ROOK, 'b': BISHOP, 'n': KNIGHT}

def move_to_uci(move: Move) -> str:
    s = rc_to_sq(move.sr, move.sc) + rc_to_sq(move.er, move.ec)
    if move.promotion is not None:
        # On encode toujours en minuscule (standard UCI) : q/r/b/n
        for k,v in _PROMO_MAP.items():
            if v == move.promotion:
                s += k
                break
    return s

def uci_to_move(state: GameState, uci: str) -> Move:
    """Convertit une chaîne UCI en Move, en retrouvant les flags via les coups légaux."""
    uci = uci.strip()
    if len(uci) < 4:
        raise ValueError(f"Coup UCI invalide: {uci}")
    sr, sc = sq_to_rc(uci[:2])
    er, ec = sq_to_rc(uci[2:4])
    promo = None
    if len(uci) >= 5:
        promo = _PROMO_MAP.get(uci[4].lower())

    # Trouver un Move correspondant parmi les coups légaux (pour récupérer en passant/roque)
    for mv in legal_moves(state):
        if (mv.sr, mv.sc, mv.er, mv.ec) == (sr, sc, er, ec):
            if promo is None and mv.promotion is None:
                return mv
            if promo is not None and mv.promotion == promo:
                return mv
            # si le moteur propose queen auto mais on demande q, ça match
            if promo is not None and mv.promotion is not None and mv.promotion == promo:
                return mv
    raise ValueError(f"Coup non légal dans cette position: {uci}")

# --- Attaques / échecs --------------------------------------------------------

def is_square_attacked(state: GameState, r:int, c:int, by_color:int) -> bool:
    """True si la case (r,c) est attaquée par la couleur by_color."""
    b = state.board
    # Pions
    if by_color == 1:
        for dc in (-1, 1):
            rr, cc = r+1, c+dc
            if in_bounds(rr,cc) and b[rr][cc] == PAWN:
                return True
    else:
        for dc in (-1, 1):
            rr, cc = r-1, c+dc
            if in_bounds(rr,cc) and b[rr][cc] == -PAWN:
                return True

    # Cavaliers
    knight = KNIGHT if by_color == 1 else -KNIGHT
    for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
        rr, cc = r+dr, c+dc
        if in_bounds(rr,cc) and b[rr][cc] == knight:
            return True

    # Roi
    king = KING if by_color == 1 else -KING
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r+dr, c+dc
            if in_bounds(rr,cc) and b[rr][cc] == king:
                return True

    # Lignes/colonnes (tours/dame)
    rook = ROOK if by_color == 1 else -ROOK
    queen = QUEEN if by_color == 1 else -QUEEN
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        rr, cc = r+dr, c+dc
        while in_bounds(rr,cc):
            p = b[rr][cc]
            if p != 0:
                if p == rook or p == queen:
                    return True
                break
            rr += dr; cc += dc

    # Diagonales (fous/dame)
    bishop = BISHOP if by_color == 1 else -BISHOP
    for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        rr, cc = r+dr, c+dc
        while in_bounds(rr,cc):
            p = b[rr][cc]
            if p != 0:
                if p == bishop or p == queen:
                    return True
                break
            rr += dr; cc += dc

    return False

def in_check(state: GameState, color:int) -> bool:
    kr, kc = state.king_pos(color)
    return is_square_attacked(state, kr, kc, by_color=opponent(color))

# --- Génération des coups ------------------------------------------------------

def generate_pseudo_moves(state: GameState, color:int) -> List[Move]:
    """Coups pseudo-légaux (sans filtrer l'auto-échec)."""
    moves: List[Move] = []
    b = state.board

    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if p == 0:
                continue
            if (p > 0 and color != 1) or (p < 0 and color != -1):
                continue

            ap = abs(p)

            if ap == PAWN:
                moves.extend(_pawn_moves(state, r, c, color))
            elif ap == KNIGHT:
                moves.extend(_knight_moves(state, r, c, color))
            elif ap == BISHOP:
                moves.extend(_slider_moves(state, r, c, color, [(-1,-1),(-1,1),(1,-1),(1,1)]))
            elif ap == ROOK:
                moves.extend(_slider_moves(state, r, c, color, [(-1,0),(1,0),(0,-1),(0,1)]))
            elif ap == QUEEN:
                moves.extend(_slider_moves(state, r, c, color, [(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)]))
            elif ap == KING:
                moves.extend(_king_moves(state, r, c, color))

    return moves

def legal_moves(state: GameState) -> List[Move]:
    """Coups légaux (filtrés pour ne pas laisser son roi en échec)."""
    color = state.turn
    moves = generate_pseudo_moves(state, color)
    out: List[Move] = []
    for mv in moves:
        ns = make_move(state, mv)
        if not in_check(ns, color):
            out.append(mv)
    return out

def _pawn_moves(state: GameState, r:int, c:int, color:int) -> List[Move]:
    b = state.board
    moves: List[Move] = []
    dir = -1 if color == 1 else 1
    start_row = 6 if color == 1 else 1
    promo_row = 0 if color == 1 else 7

    # 1 pas
    r1 = r + dir
    if in_bounds(r1,c) and b[r1][c] == 0:
        if r1 == promo_row:
            for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                moves.append(Move(r,c,r1,c, promotion=promo))
        else:
            moves.append(Move(r,c,r1,c))
        # 2 pas
        r2 = r + 2*dir
        if r == start_row and in_bounds(r2,c) and b[r2][c] == 0:
            moves.append(Move(r,c,r2,c))

    # prises diagonales
    for dc in (-1, 1):
        rr, cc = r + dir, c + dc
        if not in_bounds(rr,cc):
            continue
        target = b[rr][cc]
        if target != 0 and (target * color) < 0:
            if rr == promo_row:
                for promo in (QUEEN, ROOK, BISHOP, KNIGHT):
                    moves.append(Move(r,c,rr,cc, promotion=promo))
            else:
                moves.append(Move(r,c,rr,cc))

    # prise en passant
    if state.en_passant is not None:
        epr, epc = state.en_passant
        if epr == r + dir and abs(epc - c) == 1:
            moves.append(Move(r,c,epr,epc,is_en_passant=True))

    return moves

def _knight_moves(state: GameState, r:int, c:int, color:int) -> List[Move]:
    b = state.board
    moves: List[Move] = []
    for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
        rr, cc = r+dr, c+dc
        if not in_bounds(rr,cc):
            continue
        target = b[rr][cc]
        if target == 0 or (target * color) < 0:
            moves.append(Move(r,c,rr,cc))
    return moves

def _slider_moves(state: GameState, r:int, c:int, color:int, directions: List[Tuple[int,int]]) -> List[Move]:
    b = state.board
    moves: List[Move] = []
    for dr, dc in directions:
        rr, cc = r+dr, c+dc
        while in_bounds(rr,cc):
            target = b[rr][cc]
            if target == 0:
                moves.append(Move(r,c,rr,cc))
            else:
                if (target * color) < 0:
                    moves.append(Move(r,c,rr,cc))
                break
            rr += dr; cc += dc
    return moves

def _king_moves(state: GameState, r:int, c:int, color:int) -> List[Move]:
    b = state.board
    moves: List[Move] = []
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r+dr, c+dc
            if not in_bounds(rr,cc):
                continue
            target = b[rr][cc]
            if target == 0 or (target * color) < 0:
                moves.append(Move(r,c,rr,cc))

    # Roque
    if color == 1 and (r,c) == (7,4):
        if state.castling.wk:
            if b[7][5] == 0 and b[7][6] == 0:
                if (not in_check(state, 1) and
                    not is_square_attacked(state, 7,5, by_color=-1) and
                    not is_square_attacked(state, 7,6, by_color=-1)):
                    if b[7][7] == ROOK:
                        moves.append(Move(7,4,7,6,is_castling=True))
        if state.castling.wq:
            if b[7][1] == 0 and b[7][2] == 0 and b[7][3] == 0:
                if (not in_check(state, 1) and
                    not is_square_attacked(state, 7,3, by_color=-1) and
                    not is_square_attacked(state, 7,2, by_color=-1)):
                    if b[7][0] == ROOK:
                        moves.append(Move(7,4,7,2,is_castling=True))
    elif color == -1 and (r,c) == (0,4):
        if state.castling.bk:
            if b[0][5] == 0 and b[0][6] == 0:
                if (not in_check(state, -1) and
                    not is_square_attacked(state, 0,5, by_color=1) and
                    not is_square_attacked(state, 0,6, by_color=1)):
                    if b[0][7] == -ROOK:
                        moves.append(Move(0,4,0,6,is_castling=True))
        if state.castling.bq:
            if b[0][1] == 0 and b[0][2] == 0 and b[0][3] == 0:
                if (not in_check(state, -1) and
                    not is_square_attacked(state, 0,3, by_color=1) and
                    not is_square_attacked(state, 0,2, by_color=1)):
                    if b[0][0] == -ROOK:
                        moves.append(Move(0,4,0,2,is_castling=True))
    return moves

# --- Application des coups -----------------------------------------------------

def make_move(state: GameState, move: Move) -> GameState:
    ns = state.copy()
    apply_move_inplace(ns, move)
    return ns

def apply_move_inplace(state: GameState, move: Move) -> None:
    b = state.board
    sr, sc, er, ec = move.sr, move.sc, move.er, move.ec
    piece = b[sr][sc]
    color = 1 if piece > 0 else -1
    target = b[er][ec]

    # Historique UCI (avant modifications)
    state.move_history.append(move_to_uci(move))

    # Horloges
    if abs(piece) == PAWN or target != 0 or move.is_en_passant:
        state.halfmove_clock = 0
    else:
        state.halfmove_clock += 1
    if state.turn == -1:
        state.fullmove_number += 1

    new_en_passant: Optional[Tuple[int,int]] = None

    # Déplacement
    b[sr][sc] = 0
    if move.is_en_passant:
        b[er][ec] = piece
        captured_r = er + (1 if color == 1 else -1)
        b[captured_r][ec] = 0
    else:
        b[er][ec] = piece

    # Promotion (dame par défaut, mais UCI peut demander autre chose)
    if move.promotion is not None:
        b[er][ec] = move.promotion * color

    # Roque: déplacer la tour
    wk, wq, bk, bq = state.castling.wk, state.castling.wq, state.castling.bk, state.castling.bq
    if move.is_castling and abs(piece) == KING:
        if color == 1:
            if (sr,sc,er,ec) == (7,4,7,6):
                b[7][5] = b[7][7]; b[7][7] = 0
            elif (sr,sc,er,ec) == (7,4,7,2):
                b[7][3] = b[7][0]; b[7][0] = 0
        else:
            if (sr,sc,er,ec) == (0,4,0,6):
                b[0][5] = b[0][7]; b[0][7] = 0
            elif (sr,sc,er,ec) == (0,4,0,2):
                b[0][3] = b[0][0]; b[0][0] = 0

    # Double pas de pion => en passant
    if abs(piece) == PAWN and abs(er - sr) == 2:
        new_en_passant = ((sr + er)//2, sc)

    # Droits de roque: roi ou tours bougent / tours capturées sur cases initiales
    if piece == KING: wk = False; wq = False
    if piece == -KING: bk = False; bq = False
    if piece == ROOK:
        if (sr,sc) == (7,7): wk = False
        if (sr,sc) == (7,0): wq = False
    if piece == -ROOK:
        if (sr,sc) == (0,7): bk = False
        if (sr,sc) == (0,0): bq = False
    if target == ROOK:
        if (er,ec) == (7,7): wk = False
        if (er,ec) == (7,0): wq = False
    if target == -ROOK:
        if (er,ec) == (0,7): bk = False
        if (er,ec) == (0,0): bq = False

    state.castling = CastlingRights(wk=wk, wq=wq, bk=bk, bq=bq)
    state.en_passant = new_en_passant
    state.turn = -state.turn

# --- Fin de partie -------------------------------------------------------------

def has_legal_moves(state: GameState) -> bool:
    return len(legal_moves(state)) > 0

def is_checkmate(state: GameState) -> bool:
    return in_check(state, state.turn) and not has_legal_moves(state)

def is_stalemate(state: GameState) -> bool:
    return (not in_check(state, state.turn)) and not has_legal_moves(state)

# --- FEN ----------------------------------------------------------------------

_PIECE_TO_FEN = {
    PAWN: 'P', KNIGHT:'N', BISHOP:'B', ROOK:'R', QUEEN:'Q', KING:'K',
    -PAWN:'p', -KNIGHT:'n', -BISHOP:'b', -ROOK:'r', -QUEEN:'q', -KING:'k',
}
_FEN_TO_PIECE = {v:k for k,v in _PIECE_TO_FEN.items()}

def state_to_fen(state: GameState) -> str:
    # Piece placement
    rows = []
    for r in range(8):
        empty = 0
        out = ""
        for c in range(8):
            p = state.board[r][c]
            if p == 0:
                empty += 1
            else:
                if empty:
                    out += str(empty)
                    empty = 0
                out += _PIECE_TO_FEN[p]
        if empty:
            out += str(empty)
        rows.append(out)
    placement = "/".join(rows)
    active = "w" if state.turn == 1 else "b"
    rights = ""
    if state.castling.wk: rights += "K"
    if state.castling.wq: rights += "Q"
    if state.castling.bk: rights += "k"
    if state.castling.bq: rights += "q"
    if rights == "": rights = "-"
    ep = "-"
    if state.en_passant is not None:
        ep = rc_to_sq(*state.en_passant)
    return f"{placement} {active} {rights} {ep} {state.halfmove_clock} {state.fullmove_number}"

def fen_to_state(fen: str) -> GameState:
    parts = fen.strip().split()
    if len(parts) < 4:
        raise ValueError("FEN invalide.")
    placement, active, rights, ep = parts[0], parts[1], parts[2], parts[3]
    halfmove = int(parts[4]) if len(parts) >= 5 else 0
    fullmove = int(parts[5]) if len(parts) >= 6 else 1

    board = [[0]*8 for _ in range(8)]
    rows = placement.split("/")
    if len(rows) != 8:
        raise ValueError("FEN placement invalide.")
    for r, row in enumerate(rows):
        c = 0
        for ch in row:
            if ch.isdigit():
                c += int(ch)
            else:
                board[r][c] = _FEN_TO_PIECE[ch]
                c += 1
        if c != 8:
            raise ValueError("FEN rang invalide.")
    turn = 1 if active == "w" else -1
    castling = CastlingRights(
        wk=("K" in rights),
        wq=("Q" in rights),
        bk=("k" in rights),
        bq=("q" in rights),
    )
    en_passant = None if ep == "-" else sq_to_rc(ep)
    return GameState(board=board, turn=turn, castling=castling, en_passant=en_passant,
                     halfmove_clock=halfmove, fullmove_number=fullmove, move_history=[])