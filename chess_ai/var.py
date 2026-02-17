"""
var.py - Variables et constantes pour l'IA d'échecs
Reconstruit depuis les usages observés dans ai.py et eval.py
"""
import chess

class Variable:
    """Classe contenant les constantes de l'IA"""

    def __init__(self):
        # Valeurs des pièces en centipawns (style Stockfish)
        self.PIECE_VALUES = {
            chess.PAWN:   100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK:   500,
            chess.QUEEN:  900,
            chess.KING:     0,
        }

        # Profondeur de recherche par défaut
        self.DEPTH = 3

        # Scores de mat
        self.MATE_SCORE = 99999
        self.DRAW_SCORE = 0






