"""
gui.py — Interface Tkinter avec analyse en temps réel.
Fonctionne avec :
    engine_chess.py  (règles via python-chess)
    ai.py            (votre nouvelle IA minimax)

Modes : Humain vs IA  |  IA vs IA
Panneau d'analyse : top 5 coups, évaluation, stats nœuds/temps.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, List, Dict
import time
import chess

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

    def __init__(self, parent):
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

    def update_evaluation(self, score: float, perspective: int = 1):
        if abs(score) >= MATE_SCORE - 10:
            text  = f"Mat en {int(MATE_SCORE - abs(score))}"
            color = "green" if score > 0 else "red"
        else:
            text  = f"{score / 100.0:+.2f}" if abs(score) > 10 else f"{score:+.2f}"
            color = ("gray" if abs(score) < 0.5
                     else ("green" if score > 0 else "red"))
        self.eval_label.config(text=text, fg=color)
        self._draw_bar(score)

    def _draw_bar(self, score: float):
        c = self.eval_bar
        w = c.winfo_width() or 400
        c.delete("all")
        clamped = max(-10, min(10, score if abs(score) <= 10 else score / 100))
        ratio   = (clamped + 10) / 20.0
        x = int(w * ratio)
        c.create_rectangle(0, 0, x,  20, fill="white",  outline="")
        c.create_rectangle(x, 0, w,  20, fill="black",  outline="")
        c.create_line(w // 2, 0, w // 2, 20, fill="gray", width=2)

    def update_stats(self, nodes: int, elapsed: float):
        self.nodes_lbl.config(text=f"Nœuds: {nodes:,}")
        self.time_lbl.config(text=f"Temps: {elapsed:.2f}s")
        nps = int(nodes / elapsed) if elapsed > 0 else 0
        self.nps_lbl.config(text=f"Nœuds/s: {nps:,}")

    def update_top_moves(self, moves_data: List[Dict],
                         chosen_uci: Optional[str] = None):
        for w in self.move_widgets:
            w.destroy()
        self.move_widgets.clear()

        if not moves_data:
            lbl = tk.Label(self.moves_frame, text="Aucune analyse", fg="gray")
            lbl.pack(pady=10); self.move_widgets.append(lbl); return

        for i, d in enumerate(moves_data[:5]):
            uci   = d["move"]
            score = d["score"]
            mf    = tk.Frame(self.moves_frame, bd=1, relief="solid", padx=5, pady=3)
            mf.pack(fill="x", pady=2)
            if chosen_uci and uci == chosen_uci:
                mf.config(bg="#90EE90")

            tk.Label(mf, text=f"#{i+1}", font=("Helvetica", 9, "bold")).pack(side="left")
            tk.Label(mf, text=uci, font=("Courier", 10, "bold")).pack(side="left", padx=10)

            if abs(score) >= MATE_SCORE - 10:
                etxt = f"Mat en {int(MATE_SCORE - abs(score))}"
            elif abs(score) > 10:
                etxt = f"{score / 100.0:+.2f}"
            else:
                etxt = f"{score:+.2f}"
            tk.Label(mf, text=etxt, font=("Helvetica", 9)).pack(side="right")

            if chosen_uci and uci == chosen_uci:
                tk.Label(mf, text="✓ CHOISI", fg="green",
                         font=("Helvetica", 8, "bold")).pack(side="right", padx=5)
            self.move_widgets.append(mf)

    def clear(self):
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

    def __init__(self, root: tk.Tk):
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
        win.update_idletasks()
        x = (win.winfo_screenwidth()  - win.winfo_width())  // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # --------------------------------------------------------------- gameplay -

    def _start_game(self):
        self._refresh()
        if self.game_mode == "human_vs_ai" and self.human_color != self.state.turn:
            self.root.after(200, self.ai_play)
        elif self.game_mode == "ai_vs_ai":
            self.pause_btn.config(state="normal")
            self.ai_vs_ai_running = True
            self.ai_vs_ai_paused  = False
            self.root.after(200, self._ai_vs_ai_step)

    def _start_ai_vs_ai(self):
        self.ai_vs_ai_running = True
        self.ai_vs_ai_paused  = False
        self._start_game()

    def new_game(self):
        self.ai_vs_ai_running = False
        self.ai_vs_ai_paused  = False
        self.pause_btn.config(state="disabled", text="Pause")
        self.state = GameState(board=initial_board())
        self.selected = None
        self.legal_from_selected = []
        self.last_move = None
        self.ai_depth_white   = int(self.depth_white_var.get())
        self.ai_depth_black   = int(self.depth_black_var.get())
        self.animation_delay  = int(self.delay_var.get())
        self.analysis_panel.clear()
        self._ask_game_mode()

    def toggle_pause(self):
        if self.game_mode != "ai_vs_ai": return
        self.ai_vs_ai_paused = not self.ai_vs_ai_paused
        self.pause_btn.config(text="Reprendre" if self.ai_vs_ai_paused else "Pause")
        if not self.ai_vs_ai_paused:
            self.root.after(100, self._ai_vs_ai_step)

    def on_click(self, r: int, c: int):
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
        start = time.time()
        moves = legal_moves(self.state)
        if not moves:
            return evaluate(self.state.get_board()), [], 0, 0.0

        board       = self.state.get_board()
        tt          = {}
        moves_data  = []
        total_nodes = 0

        for move in moves:
            child_board = board.copy()
            child_board.push(move.to_chess())

            score, nodes, _ = alphabeta(
                child_board, depth - 1,
                -float("inf"), float("inf"),
                1, tt, None
            )
            score = -score  # point de vue de l'adversaire

            total_nodes += nodes
            moves_data.append({
                "move":     move_to_uci(move),
                "move_obj": move,
                "score":    score,
            })

        # Trier : meilleur coup en premier selon le camp qui joue
        reverse = (self.state.turn == 1)  # blancs = maximiser
        moves_data.sort(key=lambda x: x["score"], reverse=reverse)

        best_score = moves_data[0]["score"] if moves_data else 0.0
        elapsed    = time.time() - start
        return best_score, moves_data, total_nodes, elapsed

    def ai_play(self):
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
    root = tk.Tk()
    ChessApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()