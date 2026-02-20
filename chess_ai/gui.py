"""
commentaire général du fichier : 

C'est le fichier principal de l'application. 
Il gère tout ce que l'utilisateur voit et fait :
l'affichage de l'échiquier, les clics du joueur,
les deux modes de jeu (Humain vs IA et IA vs IA), 
et un panneau latéral qui affiche en temps réell'évaluation de la position et les meilleurscoups calculés
Il est construit avec Tkinter et fait le lien entre le moteur de règles (engine_chess.py),
 l'IA (ai.py) et le livre d'ouverture (opening_book.py)
gui.py — Interface Tkinter avec analyse en temps réel
Modes : Humain vs IA  |  IA vs IA
Panneau d'analyse : top 5 coups, évaluation, stats nœuds/temps. 


Variables :

LIGHT	:Couleur beige des cases claires de l'échiquier
DARK	:Couleur marron des cases sombres
SEL	Vert: appliqué sur la case sélectionnée par le joueur
MOVEH	:Jaune appliqué sur les destinations légales de la pièce sélectionnée
LAST	:Bleu ciel appliqué sur les deux cases du dernier coup joué

"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, List, Dict
import time
import chess
from chess_ai.opening_book import *
# ── Moteur ──────────────────────────────────────────────────────────────────
from chess_ai.engine_chess import *


# ── IA ───────────────────────────────────────────────────────────────────────
from chess_ai.ai import *
LIGHT = "#F0D9B5"
DARK  = "#B58863"
SEL   = "#77DD77"
MOVEH = "#FFD966"
LAST  = "#87CEFA"


# ============================================================
# Panneau d'analyse
# ============================================================

class AnalysisPanel(tk.Frame):

    """variables : 
    
self.eval_label	: Label affichant le score de la position (ex. +1.50 ou Mat+3)
self.eval_bar	: Canvas dessinant la barre visuelle blanc/noir proportionnelle au score
self.nodes_lbl	: Label affichant le nombre de nœuds explorés
self.time_lbl	: Label affichant le temps de calcul en secondes
self.nps_lbl	: Label affichant les nœuds par seconde (indicateur de performance)
self.moves_canvas	:Canvas contenant la zone scrollable des meilleurs coups
self.moves_frame	:Frame interne au canvas où sont placés les widgets de coups
self.move_widgets	: Liste des widgets affichés, gardés en mémoire pour pouvoir les effacer avant la prochaine mise à jour

    """

    def __init__(self, parent):
        """Crée et organise tous les widgets du panneau : titre, label de score, 
        barre graphique, labels de stats, séparateur,
          et zone scrollable pour les meilleurs coups"""
        super().__init__(parent, bd=2, relief="groove")

        tk.Label(self, text="📊 Analyse de Position",
                 font=("Helvetica", 12, "bold")).pack(pady=5)

        # Évaluation
        ef = tk.Frame(self); ef.pack(fill="x", padx=5, pady=5)
        tk.Label(ef, text="Évaluation:", font=("Helvetica", 10, "bold")).pack(side="left")
        self.eval_label = tk.Label(ef, text="0.00",
                                   font=("Helvetica", 14, "bold"), fg="blue")
        self.eval_label.pack(side="left", padx=10)

        # Barre visuelle
        self.eval_bar = tk.Canvas(self, height=20, bg="white", bd=1, relief="sunken")
        self.eval_bar.pack(fill="x", padx=5, pady=2)

        # Stats
        sf = tk.Frame(self); sf.pack(fill="x", padx=5, pady=5)
        self.nodes_lbl = tk.Label(sf, text="Nœuds: 0",    font=("Helvetica", 9)); self.nodes_lbl.pack(anchor="w")
        self.time_lbl  = tk.Label(sf, text="Temps: 0.0s", font=("Helvetica", 9)); self.time_lbl.pack(anchor="w")
        self.nps_lbl   = tk.Label(sf, text="Nœuds/s: 0",  font=("Helvetica", 9)); self.nps_lbl.pack(anchor="w")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=5)

        tk.Label(self, text="🎯 Meilleurs Coups",
                 font=("Helvetica", 10, "bold")).pack(pady=5)

        # Liste des coups
        mc = tk.Frame(self); mc.pack(fill="both", expand=True, padx=5, pady=5)
        self.moves_canvas = tk.Canvas(mc, height=200)
        sb = tk.Scrollbar(mc, orient="vertical", command=self.moves_canvas.yview)
        self.moves_frame = tk.Frame(self.moves_canvas)
        self.moves_canvas.create_window((0, 0), window=self.moves_frame, anchor="nw")
        self.moves_canvas.configure(yscrollcommand=sb.set)
        self.moves_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.moves_frame.bind("<Configure>",
            lambda e: self.moves_canvas.configure(
                scrollregion=self.moves_canvas.bbox("all")))
        self.move_widgets: List[tk.Widget] = []

    # ---- mise à jour --------------------------------------------------------

    @staticmethod
    def _safe_score(score: float) -> float:
        """Remplace les valeurs mathématiques invalides (NaN, infini)
          par ±MATE_SCORE pour éviter tout crash lors de l'affichage"""
        import math
        if math.isnan(score) or math.isinf(score):
            return MATE_SCORE if score > 0 else -MATE_SCORE
        return score

    @staticmethod
    def _score_text(score: float) -> str:
        """Convertit un score numérique brut en texte lisible : "Mat+2" si un mat est détecté,
          "+1.50" si le score est en centipions, ou la valeur directe sinon"""
        import math
        if math.isnan(score) or math.isinf(score):
            score = MATE_SCORE if score > 0 else -MATE_SCORE
        if abs(score) >= MATE_SCORE - 50:
            # plies jusqu'au mat → coups complets
            plies = int(MATE_SCORE - abs(score))
            moves = max(1, (plies + 1) // 2)
            sign  = "+" if score > 0 else "-"
            return f"Mat{sign}{moves}"
        elif abs(score) > 10:
            return f"{score / 100.0:+.2f}"
        else:
            return f"{score:+.2f}"

    def update_evaluation(self, score: float, perspective: int = 1):
        """Met à jour le label de score et la barre graphique. Choisit la couleur du texte :
          vert si avantage, rouge si désavantage, gris si position nulle"""
        
        import math
        if math.isnan(score) or math.isinf(score):
            score = MATE_SCORE if score > 0 else -MATE_SCORE
        text  = self._score_text(score)
        color = ("red" if abs(score) >= MATE_SCORE - 50 and score < 0
                 else "green" if abs(score) >= MATE_SCORE - 50
                 else "gray" if abs(score) < 0.5
                 else "green" if score > 0 else "red")
        self.eval_label.config(text=text, fg=color)
        self._draw_bar(score)

    def _draw_bar(self, score: float):
        """Dessine la barre bicolore blanc/noir sur le canvas
          Le score est limité entre -10 et +10 pour le dessin, le centre représente l'égalité"""
        import math
        c = self.eval_bar
        w = c.winfo_width() or 400
        c.delete("all")
        if math.isnan(score) or math.isinf(score):
            score = MATE_SCORE if score > 0 else -MATE_SCORE
        clamped = max(-10.0, min(10.0, score if abs(score) <= 10 else score / 100.0))
        ratio   = (clamped + 10.0) / 20.0
        x = int(w * ratio)
        c.create_rectangle(0, 0, x,  20, fill="white",  outline="")
        c.create_rectangle(x, 0, w,  20, fill="black",  outline="")
        c.create_line(w // 2, 0, w // 2, 20, fill="gray", width=2)

    def update_stats(self, nodes: int, elapsed: float):
        """Met à jour les trois labels de statistiques : 
        nombre de nœuds (avec séparateurs de milliers), temps écoulé, et nœuds par seconde"""
        self.nodes_lbl.config(text=f"Nœuds: {nodes:,}")
        self.time_lbl.config(text=f"Temps: {elapsed:.2f}s")
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        self.nps_lbl.config(text=f"Nœuds/s: {nps:,}")

    def update_top_moves(self, moves_data: List[Dict],
                         chosen_uci: Optional[str] = None):
        """Efface les anciens widgets de coups, puis recrée la liste des 5 meilleurs coups
          Surligne en vert et ajoute "✓ CHOISI" sur le coup effectivement joué par l'IA"""
        for w in self.move_widgets:
            w.destroy()
        self.move_widgets.clear()

        if not moves_data:
            lbl = tk.Label(self.moves_frame, text="Aucune analyse", fg="gray")
            lbl.pack(pady=10); self.move_widgets.append(lbl); return

        for i, d in enumerate(moves_data[:5]):
            uci   = d["move"]
            score = self._safe_score(d["score"])
            mf    = tk.Frame(self.moves_frame, bd=1, relief="solid", padx=5, pady=3)
            mf.pack(fill="x", pady=2)
            if chosen_uci and uci == chosen_uci:
                mf.config(bg="#90EE90")

            tk.Label(mf, text=f"#{i+1}", font=("Helvetica", 9, "bold")).pack(side="left")
            tk.Label(mf, text=uci, font=("Courier", 10, "bold")).pack(side="left", padx=10)
            tk.Label(mf, text=self._score_text(score),
                     font=("Helvetica", 9)).pack(side="right")

            if chosen_uci and uci == chosen_uci:
                tk.Label(mf, text="✓ CHOISI", fg="green",
                         font=("Helvetica", 8, "bold")).pack(side="right", padx=5)
            self.move_widgets.append(mf)

    def clear(self):
        """Remet tout le panneau à zéro : score à 0.00, stats vides, barre centrée, liste de coups vide"""
        self.eval_label.config(text="0.00", fg="blue")
        self.nodes_lbl.config(text="Nœuds: 0")
        self.time_lbl.config(text="Temps: 0.0s")
        self.nps_lbl.config(text="Nœuds/s: 0")
        self.update_top_moves([])
        c = self.eval_bar; w = c.winfo_width() or 400; c.delete("all")
        c.create_rectangle(0, 0, w//2, 20, fill="white", outline="")
        c.create_rectangle(w//2, 0, w, 20, fill="black", outline="")


# ============================================================
# Application principale
# ============================================================

class ChessApp:
    """variables : 
    self.root :	Fenêtre principale Tkinter
    self.state :	État courant du jeu (plateau + tour + historique)
    self.game_mode : 	Mode en cours : "human_vs_ai" ou "ai_vs_ai", None avant le choix
    self.human_color : 	Couleur du joueur humain : 1 = blancs, -1 = noirs
    self.ai_depth_white : 	Profondeur de recherche de l'IA pour les blancs
    self.ai_depth_black : 	Profondeur de recherche de l'IA pour les noirs
    self.ai_vs_ai_running : Booléen indiquant si une partie IA vs IA est en cours
    self.ai_vs_ai_paused : 	Booléen indiquant si la partie IA vs IA est en pause
    self.animation_delay : 	Délai en ms entre deux coups en mode IA vs IA
    self.selected : Coordonnées (ligne, colonne) de la case sélectionnée, None si aucune
    self.legal_from_selected :	Liste des coups légaux depuis la case sélectionnée
    self.last_move : Coordonnées (sr, sc, er, ec) du dernier coup joué
    self.status	: Label de statut au-dessus de l'échiquier (tour, mode)
    self.board_frame : 	Frame contenant les 64 boutons de l'échiquier
    self.buttons : 	Dictionnaire {(r,c): Button} pour accéder à chaque case
    self.analysis_panel : 	Instance du panneau d'analyse
    self.depth_white_var : 	Variable Tkinter liée au spinbox profondeur blancs
    self.depth_black_var : 	Variable Tkinter liée au spinbox profondeur noirs
    self.delay_var : 	Variable Tkinter liée au spinbox du délai
    self.pause_btn : 	Bouton Pause/Reprendre, désactivé en mode humain
"""

    def __init__(self, root: tk.Tk):
        """Constructeur. Initialise toutes les variables, 
        construit l'interface avec _build_interface(), puis ouvre le dialogue de choix de mode """
        self.root = root
        self.root.title("Échecs — IA python-chess")

        self.state = GameState(board=initial_board())

        self.game_mode           = None
        self.human_color         = 1
        self.ai_depth_white      = 3
        self.ai_depth_black      = 3
        self.ai_vs_ai_running    = False
        self.ai_vs_ai_paused     = False
        self.animation_delay     = 800

        self.selected: Optional[Tuple[int, int]] = None
        self.legal_from_selected: List[Move]     = []
        self.last_move: Optional[Tuple]          = None

        self._build_interface()
        self.root.after(100, self._ask_game_mode)

    # ------------------------------------------------------------------ UI --

    def _build_interface(self):
        """Construit la mise en page générale : colonne gauche (statut, 
        échiquier, contrôles avec spinboxes et boutons) et colonne droite (panneau d'analyse)"""
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.Frame(main); left.pack(side="left", padx=(0, 10))

        self.status = tk.Label(left, text="", font=("Helvetica", 12))
        self.status.pack(anchor="w", pady=5)

        self.board_frame = tk.Frame(left, bd=2, relief="groove")
        self.board_frame.pack()

        ctrl = tk.Frame(left); ctrl.pack(pady=10, fill="x")

        df = tk.Frame(ctrl); df.pack(fill="x", pady=2)
        tk.Label(df, text="Prof. Blancs:", font=("Helvetica", 9)).pack(side="left", padx=2)
        self.depth_white_var = tk.IntVar(value=3)
        tk.Spinbox(df, from_=1, to=6, textvariable=self.depth_white_var, width=3).pack(side="left", padx=2)
        tk.Label(df, text="Prof. Noirs:", font=("Helvetica", 9)).pack(side="left", padx=8)
        self.depth_black_var = tk.IntVar(value=3)
        tk.Spinbox(df, from_=1, to=6, textvariable=self.depth_black_var, width=3).pack(side="left", padx=2)

        dlf = tk.Frame(ctrl); dlf.pack(fill="x", pady=2)
        tk.Label(dlf, text="Délai (ms):", font=("Helvetica", 9)).pack(side="left", padx=2)
        self.delay_var = tk.IntVar(value=800)
        tk.Spinbox(dlf, from_=100, to=3000, increment=100,
                   textvariable=self.delay_var, width=5).pack(side="left", padx=2)

        bf = tk.Frame(ctrl); bf.pack(fill="x", pady=5)
        tk.Button(bf, text="Nouvelle partie", command=self.new_game, width=15).pack(side="left", padx=2)
        self.pause_btn = tk.Button(bf, text="Pause", command=self.toggle_pause,
                                   state="disabled", width=10)
        self.pause_btn.pack(side="left", padx=2)

        right = tk.Frame(main, width=400)
        right.pack(side="right", fill="both", expand=True)
        self.analysis_panel = AnalysisPanel(right)
        self.analysis_panel.pack(fill="both", expand=True)

        self.buttons: Dict[Tuple[int, int], tk.Button] = {}
        self._build_board()

    def _build_board(self):
        """Crée les 64 boutons de l'échiquier en grille 8×8
          Chaque bouton est relié à on_click avec ses coordonnées capturées dans un lambda"""
        for r in range(8):
            for c in range(8):
                bg  = LIGHT if (r + c) % 2 == 0 else DARK
                btn = tk.Button(
                    self.board_frame, text="",
                    font=("Segoe UI Symbol", 24), width=2, height=1, bg=bg,
                    command=lambda rr=r, cc=c: self.on_click(rr, cc))
                btn.grid(row=r, column=c)
                self.buttons[(r, c)] = btn

    # ---------------------------------------------------------------- dialogs -

    def _ask_game_mode(self):
        """Ouvre une fenêtre modale proposant les deux modes de jeu contient les fonctions internes hvai() 
        (humain vs IA → appelle _ask_side) et avai() (IA vs IA → appelle _start_ai_vs_ai)"""
        win = tk.Toplevel(self.root); win.title("Mode de jeu"); win.grab_set()
        tk.Label(win, text="Mode de jeu :", font=("Helvetica", 14, "bold")).pack(padx=20, pady=15)
        btns = tk.Frame(win); btns.pack(pady=10)

        def hvai():
            self.game_mode = "human_vs_ai"; win.destroy(); self._ask_side()
        def avai():
            self.game_mode = "ai_vs_ai"; win.destroy(); self._start_ai_vs_ai()

        tk.Button(btns, text="Humain vs IA", width=15, height=2, command=hvai).pack(pady=5)
        tk.Button(btns, text="IA vs IA",     width=15, height=2, command=avai).pack(pady=5)
        self._center(win)

    def _ask_side(self):
        """Ouvre une fenêtre modale pour choisir la couleur du joueur humain contient les fonctions internes sw() 
        (blancs, human_color = 1)et sb() (noirs, human_color = -1),
          toutes deux appelant _start_game() ensuite"""
        
        win = tk.Toplevel(self.root); win.title("Couleur"); win.grab_set()
        tk.Label(win, text="Tu joues avec :", font=("Helvetica", 12)).pack(padx=12, pady=12)
        btns = tk.Frame(win); btns.pack(pady=10)

        def sw(): self.human_color = 1;  win.destroy(); self._start_game()
        def sb(): self.human_color = -1; win.destroy(); self._start_game()

        tk.Button(btns, text="Blancs", width=10, command=sw).pack(side="left", padx=8)
        tk.Button(btns, text="Noirs",  width=10, command=sb).pack(side="left", padx=8)
        self._center(win); self.root.wait_window(win)

    @staticmethod
    def _center(win: tk.Toplevel): 
        """Méthode statique. Centre une fenêtre Toplevel au milieu de l'écran 
        en calculant les coordonnées depuis la résolution de l'écran"""
        win.update_idletasks()
        x = (win.winfo_screenwidth()  - win.winfo_width())  // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # --------------------------------------------------------------- gameplay -

    def _start_game(self):
        """Lance la partie : rafraîchit l'affichage,
          et si c'est à l'IA de commencer en premier, déclenche ai_play """
        self._refresh()
        if self.game_mode == "human_vs_ai" and self.human_color != self.state.turn:
            self.root.after(200, self.ai_play)
        elif self.game_mode == "ai_vs_ai":
            self.pause_btn.config(state="normal")
            self.ai_vs_ai_running = True
            self.ai_vs_ai_paused  = False
            self.root.after(200, self._ai_vs_ai_step)

    def _start_ai_vs_ai(self):
        """Active les flags de la partie IA vs IA puis appelle _start_game()"""
        self.ai_vs_ai_running = True
        self.ai_vs_ai_paused  = False
        self._start_game()

    def new_game(self):
        """Remet tout à zéro : arrête l'IA, réinitialise le plateau, la sélection, le dernier coup, 
        réinitialise le livre d'ouverture (reset_line()), lit les nouvelles valeurs des spinboxes,
           vide le panneau d'analyse, et rouvre le dialogue de mode"""
        
        self.ai_vs_ai_running = False
        self.ai_vs_ai_paused  = False
        self.pause_btn.config(state="disabled", text="Pause")
        self.state = GameState(board=initial_board())
        self.selected = None
        reset_line()   # 🔥 IMPORTANT
        self.ai_vs_ai_running = False
        self.legal_from_selected = []
        self.last_move = None
        self.ai_depth_white   = int(self.depth_white_var.get())
        self.ai_depth_black   = int(self.depth_black_var.get())
        self.animation_delay  = int(self.delay_var.get())
        self.analysis_panel.clear()
        self._ask_game_mode()

    def toggle_pause(self):
        """Bascule la pause en mode IA vs IA. Met à jour le texte du bouton 
        et relance _ai_vs_ai_step si on reprend"""
        if self.game_mode != "ai_vs_ai": return
        self.ai_vs_ai_paused = not self.ai_vs_ai_paused
        self.pause_btn.config(text="Reprendre" if self.ai_vs_ai_paused else "Pause")
        if not self.ai_vs_ai_paused:
            self.root.after(100, self._ai_vs_ai_step)

    def on_click(self, r: int, c: int):
        """Gère les clics en mode humain. Premier clic : sélectionne la pièce 
        et calcule les coups légaux. Deuxième clic sur une destination valide : 
        joue le coup, rafraîchit, vérifie la fin de partie, puis déclenche ai_play"""

        if self.game_mode != "human_vs_ai": return
        if self.state.turn != self.human_color: return

        self.ai_depth_white = int(self.depth_white_var.get())
        self.ai_depth_black = int(self.depth_black_var.get())

        moves  = legal_moves(self.state)
        board  = self.state.board
        piece  = board[r][c]

        if self.selected is None:
            if piece != 0 and (piece * self.human_color) > 0:
                self.selected = (r, c)
                self.legal_from_selected = [m for m in moves if (m.sr, m.sc) == (r, c)]
                self._refresh()
            return

        if self.selected == (r, c):
            self.selected = None; self.legal_from_selected = []; self._refresh(); return

        if piece != 0 and (piece * self.human_color) > 0:
            self.selected = (r, c)
            self.legal_from_selected = [m for m in moves if (m.sr, m.sc) == (r, c)]
            self._refresh(); return

        chosen = next((m for m in self.legal_from_selected if (m.er, m.ec) == (r, c)), None)
        if chosen is None: return

        apply_move_inplace(self.state, chosen)
        self.last_move = (chosen.sr, chosen.sc, chosen.er, chosen.ec)
        self.selected = None; self.legal_from_selected = []
        self._refresh()
        if self._check_end(): return
        self.root.after(100, self.ai_play)

    # --------------------------------------------------------------- analyse -

    def _analyze_position(self, depth: int):
        """Cœur de l'analyse. Consulte d'abord le livre d'ouverturze
          Si hors livre, évalue chaque coup légal en lançant negamax sur la position après ce coup
            (avec le score inversé pour revenir au point de vue du joueur actif),
              trie les résultats et retourne le meilleur score, la liste des coups, 
              le nombre de nœuds et le temps écoulé"""
        board = self.state.get_board()
        history = get_history_uci(board)

        # 🔒 Livre d’ouverture
        if len(history) < 6:
            book_move_uci = pick_book_move(
                history,
                is_white=(board.turn == chess.WHITE)
            )

            if book_move_uci:
                # 🔁 Conversion UCI → Move (engine)
                mv = chess.Move.from_uci(book_move_uci)
                sr = 7 - chess.square_rank(mv.from_square)
                sc = chess.square_file(mv.from_square)
                er = 7 - chess.square_rank(mv.to_square)
                ec = chess.square_file(mv.to_square)

                engine_move = Move(sr, sc, er, ec)

                return 0, [{
                    "move": book_move_uci,
                    "move_obj": engine_move,
                    "score": 0
                }], 1, 0.0
            
        start       = time.time()
        moves       = legal_moves(self.state)
        if not moves:
            return evaluate(self.state.get_board()), [], 0, 0.0

        board       = self.state.get_board()
        nodes_ref   = [0]
        moves_data  = []

        # ── Évaluer chaque coup racine individuellement ──────────────────────
        # On joue chaque coup, on lance negamax sur le nœud enfant avec ply=1,
        # et on récupère le score DEPUIS CET ENFANT (point de vue adversaire).
        # Le score de mat est alors cohérent : -(MATE_SCORE - ply_interne)
        # avec ply_interne >= 1, donc MATE_SCORE - abs(score) >= 1 → correct.
        for move in moves:
            child_board = board.copy()
            child_board.push(move.to_chess())

            # negamax retourne le score du joueur actif dans child_board
            score, _ = negamax(
                child_board,
                depth - 1,
                -float("inf"), float("inf"),
                nodes_ref,
                ply=1,          # ply=1 : on est déjà à 1 coup de la racine
                weights=None
            )
            # Inverser : ramener au point de vue du joueur qui joue en racine
            score = -score

            moves_data.append({
                "move":     move_to_uci(move),
                "move_obj": move,
                "score":    score,
            })

        # Trier du meilleur au pire (score le plus élevé = meilleur pour
        # le joueur actif, convention negamax)
        moves_data.sort(key=lambda x: x["score"], reverse=True)

        best_score = moves_data[0]["score"] if moves_data else 0.0
        elapsed    = time.time() - start
        return best_score, moves_data, nodes_ref[0], elapsed

    def ai_play(self):
        """Fait jouer l'IA un coup en mode Humain vs IA : appelle _analyze_position,
          choisit le meilleur coup, met à jour le panneau d'analyse, applique le coup
            et vérifie la fin de partie"""

        if self._check_end(): return
        if self.state.turn == self.human_color: return

        depth = self.ai_depth_white if self.state.turn == 1 else self.ai_depth_black
        best_score, moves_data, nodes, elapsed = self._analyze_position(depth)

        if not moves_data: self._check_end(); return

        chosen = moves_data[0]
        self.analysis_panel.update_evaluation(best_score, self.state.turn)
        self.analysis_panel.update_stats(nodes, elapsed)
        self.analysis_panel.update_top_moves(moves_data, chosen["move"])

        apply_move_inplace(self.state, chosen["move_obj"])
        self.last_move = (chosen["move_obj"].sr, chosen["move_obj"].sc,
                          chosen["move_obj"].er, chosen["move_obj"].ec)
        self._refresh(); self._check_end()

    def _ai_vs_ai_step(self):
        """"Fait jouer un coup en mode IA vs IA
          Identique à ai_play, mais se reprogramme elle-même via root.after(delay, ...) 
          pour enchaîner les coups automatiquement avec le délai configuré"""
        
        if not self.ai_vs_ai_running or self.ai_vs_ai_paused: return
        if self._check_end():
            self.ai_vs_ai_running = False; self.pause_btn.config(state="disabled"); return

        depth = self.ai_depth_white if self.state.turn == 1 else self.ai_depth_black
        best_score, moves_data, nodes, elapsed = self._analyze_position(depth)

        if not moves_data:
            self._check_end(); self.ai_vs_ai_running = False
            self.pause_btn.config(state="disabled"); return

        chosen = moves_data[0]
        self.analysis_panel.update_evaluation(best_score, self.state.turn)
        self.analysis_panel.update_stats(nodes, elapsed)
        self.analysis_panel.update_top_moves(moves_data, chosen["move"])

        apply_move_inplace(self.state, chosen["move_obj"])
        self.last_move = (chosen["move_obj"].sr, chosen["move_obj"].sc,
                          chosen["move_obj"].er, chosen["move_obj"].ec)
        self._refresh()
        self.animation_delay = int(self.delay_var.get())
        self.root.after(self.animation_delay, self._ai_vs_ai_step)

    # --------------------------------------------------------------- fin -----

    def _check_end(self) -> bool:
        """Vérifie si la partie est terminée (échec et mat, pat, matériel insuffisant,
          règle des 50 coups) affiche un message informatif et retourne True si la partie 
          est finie, False sinon"""
        
        b = self.state.get_board()
        if b.is_checkmate():
            winner = "Noirs" if self.state.turn == 1 else "Blancs"
            messagebox.showinfo("Fin de partie", f"Échec et mat ! Gagnant : {winner}")
            self.ai_vs_ai_running = False; self.pause_btn.config(state="disabled")
            return True
        if b.is_stalemate():
            messagebox.showinfo("Fin de partie", "Pat (égalité).")
            self.ai_vs_ai_running = False; self.pause_btn.config(state="disabled")
            return True
        if b.is_insufficient_material():
            messagebox.showinfo("Fin de partie", "Matériel insuffisant (nulle).")
            self.ai_vs_ai_running = False; self.pause_btn.config(state="disabled")
            return True
        if b.can_claim_fifty_moves():
            messagebox.showinfo("Fin de partie", "Règle des 50 coups (nulle).")
            self.ai_vs_ai_running = False; self.pause_btn.config(state="disabled")
            return True
        return False

    # --------------------------------------------------------------- refresh --

    def _refresh(self): 
        """Redessine les 64 cases : calcule la couleur de fond de chacune 
        (normale, sélection, coup légal, dernier coup) et met à jour le symbole Unicode 
        de la pièce présente"""

        who = "Blancs" if self.state.turn == 1 else "Noirs"
        if self.game_mode == "human_vs_ai":
            hstr = "Blancs" if self.human_color == 1 else "Noirs"
            self.status.config(text=f"Tour: {who} | Humain: {hstr}")
        else:
            self.status.config(text=f"Tour: {who} | Coup #{len(self.state.move_history)}")

        dests = {(m.er, m.ec) for m in self.legal_from_selected}
        board = self.state.board

        for r in range(8):
            for c in range(8):
                bg = LIGHT if (r + c) % 2 == 0 else DARK
                if self.last_move:
                    sr, sc, er, ec = self.last_move
                    if (r, c) in [(sr, sc), (er, ec)]:
                        bg = LAST
                if self.selected == (r, c):
                    bg = SEL
                elif (r, c) in dests:
                    bg = MOVEH

                # Récupérer le symbole depuis la pièce python-chess
                chess_board = self.state.get_board()
                sq          = chess.square(c, 7 - r)
                piece_obj   = chess_board.piece_at(sq)
                symbol      = piece_symbol(piece_obj) if piece_obj else " "

                self.buttons[(r, c)].config(bg=bg, text=symbol)


def main():

    """Point d'entrée : crée la fenêtre Tkinter,
      instancie ChessApp et lance la boucle principale avec root.mainloop()"""
    root = tk.Tk()
    ChessApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()