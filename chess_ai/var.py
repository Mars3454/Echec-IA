"""
commentaire général du fichier : Ce fichier centralise toutes les constantes numériques utilisées par l'IA, 
regroupées dans une classe Variable, l'intérêt de ce regroupement est de pouvoir modifier facilement les paramètres
 (valeurs des pièces, profondeur de recherche, scores de mat) sans avoir à chercher dans tous les fichiers
   C'est une bonne pratique de conception qui facilite le réglage et l'équilibrage de l'IA

"""
import chess

class Variable:
    """Classe contenant les constantes de l'IA 
    
    variables : 
    self.PIECE_VALUES	 =Dictionnaire :	Valeur en centipions de chaque type de pièce : pion=100, cavalier=320, fou=330, tour=500, dame=900, roi=0. Ces valeurs sont inspirées du style Stockfish
        self.DEPTH = 	4 :  Profondeur de recherche minimax par défaut (en demi-coups). Plus elle est grande, plus l'IA est forte mais lente
        self.MATE_SCORE	 = 99999 : 	Score absolu représentant une position de mat. Utilisé comme borne dans l'algorithme negamax pour distinguer un mat d'un simple avantage matériel
        self.DRAW_SCORE	= 0 : 	Score d'une position nulle (pat, répétition, etc.)
"""

    def __init__(self):
        """Unique méthode de la classe. Constructeur qui initialise et 
        définit toutes les constantes de l'IA : les valeurs des pièces dans
          un dictionnaire indexé par les types python-chess (chess.PAWN, chess.QUEEN...), 
        la profondeur par défaut, et les scores spéciaux pour le mat et la nulle"""
        self.PIECE_VALUES = {
            chess.PAWN:   100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK:   500,
            chess.QUEEN:  900,
            chess.KING:     0,
        }

        # Profondeur de recherche par défaut
        self.DEPTH = 4

        # Scores de mat
        self.MATE_SCORE = 99999
        self.DRAW_SCORE = 0






