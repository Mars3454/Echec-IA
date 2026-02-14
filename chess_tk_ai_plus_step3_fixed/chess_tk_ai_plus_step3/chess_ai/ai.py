"""
ai.py - IA Minimax + Alpha-Beta + optimisations:
- Petit livre d'ouvertures (opening_book.py) pour les premiers coups
- Évaluation améliorée: matériel + principes d'ouverture (centre, développement, sécurité du roi)
- Table de transposition (cache) pour accélérer la recherche
- Tri de coups: captures/promotions d'abord + dernier meilleur coup (TT)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import math
import time

from .engine import (
    GameState, Move, legal_moves, make_move,
    is_checkmate, is_stalemate, in_check,
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
)
from .opening_book import pick_book_move
from .weights import get_best_weights
from .engine import uci_to_move, state_to_fen

PIECE_VALUES = {
    PAWN: 100,
    KNIGHT: 320,
    BISHOP: 330,
    ROOK: 500,
    QUEEN: 900,
    KING: 0,
}

MATE_SCORE = 50_000
DRAW_SCORE = 0

# -------------------- Évaluation améliorée --------------------

CENTER_SQUARES = {(4,3), (4,4), (3,3), (3,4)}  # d4,e4,d5,e5 en (r,c)
EXT_CENTER = {(5,2),(5,3),(5,4),(5,5),(4,2),(4,5),(3,2),(3,5),(2,2),(2,3),(2,4),(2,5)}

WHITE_MINOR_START = {(7,1),(7,6),(7,2),(7,5)}  # Nb1,Ng1,Bc1,Bf1
BLACK_MINOR_START = {(0,1),(0,6),(0,2),(0,5)}  # Nb8,Ng8,Bc8,Bf8

def _is_castled(state: GameState, color: int) -> bool:
    """Détecte un roque (heuristique simple sur position du roi)."""
    kr,kc = state.king_pos(color)
    if color == 1:
        return (kr,kc) in [(7,6),(7,2)]
    return (kr,kc) in [(0,6),(0,2)]

def evaluate(state: GameState, ply: int, weights: dict | None = None) -> int:
    """
    Score du point de vue des blancs (positif => blanc mieux).
    ply: profondeur depuis la racine, pour préférer un mat rapide.
    """
    if is_checkmate(state):
        # Au joueur de jouer et mat => il perd
        return (-MATE_SCORE + ply) if state.turn == 1 else (MATE_SCORE - ply)
    if is_stalemate(state):
        return DRAW_SCORE

    W = weights if weights is not None else get_best_weights()

    center_main = int(W.get("center_main", 20))
    center_ext  = int(W.get("center_ext", 5))
    develop     = int(W.get("develop", 15))
    castled     = int(W.get("castled", 30))
    queen_early = int(W.get("queen_early", 10))
    mobility_w  = int(W.get("mobility", 1))
    in_check_w  = int(W.get("in_check", 25))

    score = 0

    # 1) Matériel
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p == 0:
                continue
            v = PIECE_VALUES[abs(p)]
            score += v if p > 0 else -v

    # 2) Contrôle/occupation du centre (ouverture)
    # bonus faible pour éviter de casser les fins de partie
    center_bonus = 0
    for (r,c) in CENTER_SQUARES:
        p = state.board[r][c]
        if p > 0: center_bonus += center_main
        elif p < 0: center_bonus -= center_main
    for (r,c) in EXT_CENTER:
        p = state.board[r][c]
        if p > 0: center_bonus += center_ext
        elif p < 0: center_bonus -= center_ext
    score += center_bonus

    # 3) Développement (cavaliers/fous sortis)
    undeveloped_w = 0
    undeveloped_b = 0
    for (r,c) in WHITE_MINOR_START:
        if abs(state.board[r][c]) in (KNIGHT, BISHOP) and state.board[r][c] > 0:
            undeveloped_w += 1
    for (r,c) in BLACK_MINOR_START:
        if abs(state.board[r][c]) in (KNIGHT, BISHOP) and state.board[r][c] < 0:
            undeveloped_b += 1
    # plus tu développes, mieux c'est
    score += develop * (undeveloped_b - undeveloped_w)

    # 4) Sécurité du roi (roque)
    if _is_castled(state, 1): score += castled
    if _is_castled(state, -1): score -= castled

    # 5) Dame trop tôt (pénalité si dame sortie alors que pièces mineures pas développées)
    # Blanc: dame au départ (7,3); Noir: (0,3)
    if state.board[7][3] != QUEEN and undeveloped_w > 0:
        score -= queen_early * undeveloped_w
    if state.board[0][3] != -QUEEN and undeveloped_b > 0:
        score += queen_early * undeveloped_b

    # 6) Petit bonus de mobilité (nombre de coups légaux)
    # léger pour limiter coût; on estime seulement au noeud courant
    try:
        lm = len(legal_moves(state))
        score += (lm if state.turn == 1 else -lm) * mobility_w
    except Exception:
        pass

    # 7) Pénalité si en échec
    if in_check(state, 1): score -= in_check_w
    if in_check(state, -1): score += in_check_w

    return score

# -------------------- Tri de coups --------------------

def order_moves(state: GameState, moves: List[Move], tt_best: Optional[Move]) -> List[Move]:
    """Captures/promotions d'abord + meilleur coup TT en tête si dispo."""
    b = state.board

    def move_key(m: Move):
        target = b[m.er][m.ec]
        moved = b[m.sr][m.sc]
        capture_value = PIECE_VALUES.get(abs(target), 0)
        moved_value = PIECE_VALUES.get(abs(moved), 0)
        promo_bonus = 800 if m.promotion is not None else 0
        ep_bonus = 50 if m.is_en_passant else 0
        castling_bonus = 30 if m.is_castling else 0
        return (capture_value * 10 - moved_value) + promo_bonus + ep_bonus + castling_bonus

    moves_sorted = sorted(moves, key=move_key, reverse=(state.turn == 1))
    if tt_best is not None:
        # place en tête si présent
        for i, m in enumerate(moves_sorted):
            if (m.sr,m.sc,m.er,m.ec,m.promotion,m.is_en_passant,m.is_castling) == (tt_best.sr,tt_best.sc,tt_best.er,tt_best.ec,tt_best.promotion,tt_best.is_en_passant,tt_best.is_castling):
                moves_sorted.insert(0, moves_sorted.pop(i))
                break
    return moves_sorted

# -------------------- Table de transposition --------------------

@dataclass
class TTEntry:
    depth: int
    score: int
    flag: str  # "EXACT", "LOWER", "UPPER"
    best: Optional[Move]

TransTable = Dict[str, TTEntry]  # clé simple = FEN

# -------------------- Recherche alpha-bêta --------------------

@dataclass
class SearchResult:
    move: Optional[Move]
    score: int
    nodes: int

def alphabeta(state: GameState, depth: int, alpha: int, beta: int, ply: int, tt: TransTable, weights: dict | None) -> Tuple[int,int, Optional[Move]]:
    nodes = 1
    key = state_to_fen(state)

    # TT lookup
    entry = tt.get(key)
    if entry is not None and entry.depth >= depth:
        if entry.flag == "EXACT":
            return entry.score, nodes, entry.best
        if entry.flag == "LOWER":
            alpha = max(alpha, entry.score)
        elif entry.flag == "UPPER":
            beta = min(beta, entry.score)
        if alpha >= beta:
            return entry.score, nodes, entry.best

    if depth == 0:
        sc = evaluate(state, ply, weights=weights)
        tt[key] = TTEntry(depth=depth, score=sc, flag="EXACT", best=None)
        return sc, nodes, None

    moves = legal_moves(state)
    if not moves:
        sc = evaluate(state, ply, weights=weights)
        tt[key] = TTEntry(depth=depth, score=sc, flag="EXACT", best=None)
        return sc, nodes, None

    tt_best = entry.best if entry else None
    moves = order_moves(state, moves, tt_best)

    best_move: Optional[Move] = None
    original_alpha = alpha
    original_beta = beta

    if state.turn == 1:
        best = -math.inf
        for mv in moves:
            child = make_move(state, mv)
            val, n, _ = alphabeta(child, depth-1, alpha, beta, ply+1, tt, weights)
            nodes += n
            if val > best:
                best = val
                best_move = mv
            alpha = max(alpha, best)
            if alpha >= beta:
                break
    else:
        best = math.inf
        for mv in moves:
            child = make_move(state, mv)
            val, n, _ = alphabeta(child, depth-1, alpha, beta, ply+1, tt, weights)
            nodes += n
            if val < best:
                best = val
                best_move = mv
            beta = min(beta, best)
            if alpha >= beta:
                break

    # Store TT
    flag = "EXACT"
    if best <= original_alpha:
        flag = "UPPER"
    elif best >= original_beta:
        flag = "LOWER"
    tt[key] = TTEntry(depth=depth, score=int(best), flag=flag, best=best_move)

    return int(best), nodes, best_move

def choose_best_move(state: GameState, depth: int, weights: dict | None = None) -> SearchResult:
    """
    Choix du meilleur coup:
    1) Tentative livre d'ouvertures si on est encore dans les premiers coups.
    2) Sinon alphabeta.
    """
    # Livre d'ouvertures uniquement dans les ~10 premiers coups (20 plies)
    if len(state.move_history) <= 20:
        uci = pick_book_move(state.move_history)
        if uci is not None:
            try:
                mv = uci_to_move(state, uci)
                # score approximatif (éval actuelle)
                return SearchResult(move=mv, score=evaluate(state, 0, weights=None), nodes=1)
            except Exception:
                pass

    tt: TransTable = {}
    score, nodes, best = alphabeta(state, depth, -MATE_SCORE, MATE_SCORE, 0, tt, weights)
    return SearchResult(move=best, score=score, nodes=nodes)

def choose_best_move_timed(state: GameState, movetime_ms: int, max_depth: int = 6, weights: dict | None = None) -> SearchResult:
    """
    Recherche itérative (iterative deepening) jusqu'à movetime_ms.
    Utile pour UCI 'go movetime ...' (approximatif).
    """
    start = time.time()
    tt: TransTable = {}
    best: Optional[Move] = None
    best_score = 0
    nodes_total = 0

    for depth in range(1, max_depth+1):
        if (time.time() - start) * 1000 >= movetime_ms:
            break
        score, nodes, mv = alphabeta(state, depth, -MATE_SCORE, MATE_SCORE, 0, tt, weights)
        nodes_total += nodes
        if mv is not None:
            best = mv
            best_score = score

    return SearchResult(move=best, score=int(best_score), nodes=nodes_total)