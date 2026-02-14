"""
gui.py - Interface Tkinter.
- Clic 1: sélectionner une pièce
- Clic 2: choisir une destination (parmi les coups légaux)
- L'IA joue automatiquement après le coup humain.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Tuple, List, Dict

from .engine import GameState, initial_board, piece_symbol, legal_moves, apply_move_inplace, is_checkmate, is_stalemate
from .ai import choose_best_move

LIGHT = "#F0D9B5"
DARK  = "#B58863"
SEL   = "#77DD77"
MOVEH = "#FFD966"
LAST  = "#87CEFA"

class ChessApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Échecs - IA (Livre + Alpha-Bêta + Optimisations)")

        self.state = GameState(board=initial_board(), turn=1)

        self.human_color = self._ask_side()  # 1 ou -1
        self.ai_depth = 3

        self.selected: Optional[Tuple[int,int]] = None
        self.legal_from_selected: List[tuple] = []
        self.last_move: Optional[tuple] = None

        top = tk.Frame(root)
        top.pack(padx=10, pady=10)

        self.status = tk.Label(top, text="", font=("Helvetica", 12))
        self.status.pack(anchor="w")

        self.board_frame = tk.Frame(top, bd=2, relief="groove")
        self.board_frame.pack()

        bottom = tk.Frame(root)
        bottom.pack(padx=10, pady=(0,10), fill="x")

        tk.Label(bottom, text="Profondeur IA:", font=("Helvetica", 10)).pack(side="left")
        self.depth_var = tk.IntVar(value=self.ai_depth)
        depth_spin = tk.Spinbox(bottom, from_=1, to=6, textvariable=self.depth_var, width=3)
        depth_spin.pack(side="left", padx=6)

        tk.Button(bottom, text="Nouvelle partie", command=self.new_game).pack(side="left", padx=6)

        self.nodes_label = tk.Label(bottom, text="", font=("Helvetica", 10))
        self.nodes_label.pack(side="right")

        self.buttons: Dict[Tuple[int,int], tk.Button] = {}
        self._build_board()
        self._refresh()

        if self.human_color != self.state.turn:
            self.root.after(200, self.ai_play)

    def _ask_side(self) -> int:
        win = tk.Toplevel(self.root)
        win.title("Choisis ta couleur")
        win.grab_set()
        choice = {"color": 1}

        tk.Label(win, text="Tu veux jouer avec :", font=("Helvetica", 12)).pack(padx=12, pady=12)

        def set_white():
            choice["color"] = 1
            win.destroy()

        def set_black():
            choice["color"] = -1
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=10)
        tk.Button(btns, text="Blancs", width=10, command=set_white).pack(side="left", padx=8)
        tk.Button(btns, text="Noirs", width=10, command=set_black).pack(side="left", padx=8)

        self.root.wait_window(win)
        return choice["color"]

    def _build_board(self):
        for r in range(8):
            for c in range(8):
                bg = LIGHT if (r+c)%2==0 else DARK
                btn = tk.Button(
                    self.board_frame,
                    text="",
                    font=("Segoe UI Symbol", 24),
                    width=2,
                    height=1,
                    bg=bg,
                    command=lambda rr=r, cc=c: self.on_click(rr,cc)
                )
                btn.grid(row=r, column=c, padx=0, pady=0)
                self.buttons[(r,c)] = btn

    def new_game(self):
        self.state = GameState(board=initial_board(), turn=1)
        self.selected = None
        self.legal_from_selected = []
        self.last_move = None
        self.ai_depth = int(self.depth_var.get())
        self.nodes_label.config(text="")
        self._refresh()
        if self.human_color != self.state.turn:
            self.root.after(200, self.ai_play)

    def on_click(self, r:int, c:int):
        if self.state.turn != self.human_color:
            return

        self.ai_depth = int(self.depth_var.get())
        moves = legal_moves(self.state)
        piece = self.state.board[r][c]

        if self.selected is None:
            if piece != 0 and (piece * self.human_color) > 0:
                self.selected = (r,c)
                self.legal_from_selected = [m for m in moves if (m.sr, m.sc) == (r,c)]
                self._refresh()
            return

        if self.selected == (r,c):
            self.selected = None
            self.legal_from_selected = []
            self._refresh()
            return

        if piece != 0 and (piece * self.human_color) > 0:
            self.selected = (r,c)
            self.legal_from_selected = [m for m in moves if (m.sr, m.sc) == (r,c)]
            self._refresh()
            return

        chosen = None
        for m in self.legal_from_selected:
            if (m.er, m.ec) == (r,c):
                chosen = m
                break
        if chosen is None:
            return

        apply_move_inplace(self.state, chosen)
        self.last_move = (chosen.sr, chosen.sc, chosen.er, chosen.ec)
        self.selected = None
        self.legal_from_selected = []
        self._refresh()

        if self._check_end():
            return

        self.root.after(100, self.ai_play)

    def ai_play(self):
        if self._check_end():
            return
        if self.state.turn == self.human_color:
            return

        self.ai_depth = int(self.depth_var.get())
        res = choose_best_move(self.state, depth=self.ai_depth)
        self.nodes_label.config(text=f"IA nœuds: {res.nodes:,} | score: {res.score}")
        if res.move is None:
            self._check_end()
            return

        apply_move_inplace(self.state, res.move)
        self.last_move = (res.move.sr, res.move.sc, res.move.er, res.move.ec)
        self._refresh()
        self._check_end()

    def _check_end(self) -> bool:
        if is_checkmate(self.state):
            winner = "Noirs" if self.state.turn == 1 else "Blancs"
            messagebox.showinfo("Fin", f"Échec et mat ! Gagnant : {winner}")
            return True
        if is_stalemate(self.state):
            messagebox.showinfo("Fin", "Pat (égalité).")
            return True
        return False

    def _refresh(self):
        who = "Blancs" if self.state.turn == 1 else "Noirs"
        self.status.config(text=f"Tour: {who} | Humain: {'Blancs' if self.human_color==1 else 'Noirs'}")

        dests = {(m.er, m.ec) for m in self.legal_from_selected}
        for r in range(8):
            for c in range(8):
                base = LIGHT if (r+c)%2==0 else DARK
                bg = base
                if self.last_move is not None:
                    sr, sc, er, ec = self.last_move
                    if (r,c) in [(sr,sc),(er,ec)]:
                        bg = LAST
                if self.selected == (r,c):
                    bg = SEL
                elif (r,c) in dests:
                    bg = MOVEH
                self.buttons[(r,c)].config(bg=bg, text=piece_symbol(self.state.board[r][c]))
