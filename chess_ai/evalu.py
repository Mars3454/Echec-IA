import chess
from chess_ai.var import Variable

variable = Variable()

CENTER = [chess.D4, chess.E4, chess.D5, chess.E5]

WEIGHTS = {
    "opening": {
        "material": 1.0,
        "center": 1.2,
        "development": 1.3,
        "king_safety": 0.8,
        "mobility": 0.5,
        "pawns": 0.6,
    },
    "middlegame": {
        "material": 1.1,
        "center": 1.0,
        "development": 0.7,
        "king_safety": 1.2,
        "mobility": 1.0,
        "pawns": 1.0,
    },
    "endgame": {
        "material": 1.3,
        "center": 0.5,
        "development": 0.0,
        "king_safety": 0.6,
        "mobility": 1.2,
        "pawns": 1.4,
    }
}


def game_phase(board):
    material = 0
    for p in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        material += len(board.pieces(p, chess.WHITE))
        material += len(board.pieces(p, chess.BLACK))
    if material > 20:
        return "opening"
    elif material > 10:
        return "middlegame"
    else:
        return "endgame"


def king_safety(board, color):
    king = board.king(color)
    if king is None:
        return -5
    safety = 0
    for sq in board.attacks(king):
        if board.is_attacked_by(not color, sq):
            safety -= 0.2
    if board.has_castling_rights(color):
        safety += 0.5
    return safety


def mobility(board, color):
    board_turn = board.turn
    board.turn = color
    moves = board.legal_moves.count()
    board.turn = board_turn
    return moves * 0.05


def pawn_structure_score(board, color):
    score = 0
    pawns = board.pieces(chess.PAWN, color)
    for file in range(8):
        pawns_in_file = [p for p in pawns if chess.square_file(p) == file]
        if len(pawns_in_file) > 1:
            score -= 0.3 * (len(pawns_in_file) - 1)
        for p in pawns_in_file:
            rank = chess.square_rank(p)
            direction = 1 if color == chess.WHITE else -1
            blocked = False
            for f in [file - 1, file, file + 1]:
                if 0 <= f <= 7:
                    r_range = range(rank + direction, 8, direction) if color == chess.WHITE else range(rank + direction, -1, direction)
                    for r in r_range:
                        sq = chess.square(f, r)
                        if sq in board.pieces(chess.PAWN, not color):
                            blocked = True
                            break
                if blocked:
                    break
            if not blocked:
                score += 0.5
            isolated = True
            for af in [file - 1, file + 1]:
                if 0 <= af <= 7:
                    if any(chess.square_file(p2) == af for p2 in pawns):
                        isolated = False
                        break
            if isolated:
                score -= 0.3
    return score


def evaluate_board(board: chess.Board):
    if board.is_checkmate():
        return 9999 if board.turn == chess.WHITE else -9999
    if board.is_stalemate():
        return 0
    if board.is_insufficient_material():
        return 0

    phase = game_phase(board)
    w = WEIGHTS[phase]
    score = 0

    black_material = sum(len(board.pieces(p, chess.BLACK)) * variable.PIECE_VALUES[p] for p in variable.PIECE_VALUES)
    white_material = sum(len(board.pieces(p, chess.WHITE)) * variable.PIECE_VALUES[p] for p in variable.PIECE_VALUES)
    score += w["material"] * (black_material - white_material)

    black_center = sum(board.is_attacked_by(chess.BLACK, sq) for sq in CENTER)
    white_center = sum(board.is_attacked_by(chess.WHITE, sq) for sq in CENTER)
    score += w["center"] * (black_center - white_center) * 0.3

    if phase == "opening":
        score += w["development"] * (
            len(board.pieces(chess.KNIGHT, chess.BLACK)) * 0.3
            - len(board.pieces(chess.KNIGHT, chess.WHITE)) * 0.3
            + len(board.pieces(chess.BISHOP, chess.BLACK)) * 0.3
            - len(board.pieces(chess.BISHOP, chess.WHITE)) * 0.3
        )

    score += w["king_safety"] * (king_safety(board, chess.BLACK) - king_safety(board, chess.WHITE))

    if phase in ["middlegame", "endgame"]:
        score += w["mobility"] * (mobility(board, chess.BLACK) - mobility(board, chess.WHITE))

    if board.is_check():
        score += 0.5 if board.turn == chess.BLACK else -0.5

    if phase == "endgame":
        bk = board.king(chess.BLACK)
        wk = board.king(chess.WHITE)
        if bk:
            score += 0.1 * len(board.attacks(bk))
        if wk:
            score -= 0.1 * len(board.attacks(wk))

    score += w["pawns"] * pawn_structure_score(board, chess.BLACK)
    score -= w["pawns"] * pawn_structure_score(board, chess.WHITE)

    return score