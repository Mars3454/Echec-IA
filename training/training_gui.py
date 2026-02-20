"""
training_gui.py - Interface d'entrainement pour la nouvelle IA python-chess.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, List
import threading, json, os, time, random
import sys
import chess

from chess_ai.engine_chess import GameState, initial_board, apply_move_inplace
from chess_ai.ai import choose_best_move_timed, set_active_weights
from training.weights import *


class TrainingThread(threading.Thread):
    def __init__(self, app, mode):
        super().__init__(daemon=True)
        self.app = app
        self.mode = mode
        self.running = True
        self.paused = False

    def run(self):
        if self.mode == "training":
            self._run_training()
        else:
            self._run_match()

    def _run_training(self):
        app = self.app
        try:
            gen = app.current_generation
            best = app.best_weights.copy()
            for it in range(1, app.max_iterations + 1):
                if not self.running:
                    break
                while self.paused and self.running:
                    time.sleep(0.1)
                if not self.running:
                    break
                app.update_log(f"[Generation {gen}] Iteration {it}/{app.max_iterations}")
                cand = self._mutate(best, app.mutation_step)
                wr, stats = self._eval_match(best, cand)
                ok = wr >= (0.5 + app.accept_margin)
                if ok:
                    gen += 1
                    app.current_generation = gen
                    best = cand.copy()
                    app.best_weights = best.copy()
                    p = gen_path(gen)
                    save_gen(p, gen, best, name=f"gen_{gen}")
                    set_best(p)
                    app.update_log(f"  ACCEPTE WR={wr:.1%} -> Gen {gen}")
                else:
                    app.update_log(f"  Rejete WR={wr:.1%}")
                app.add_training_stats({
                    "iteration": it, "generation": gen,
                    "winrate": wr, "accepted": ok, **stats
                })
                app.update_progress(it, app.max_iterations)
            app.update_log(f"\nTermine ! Meilleure generation : {gen}")
            app.training_finished()
        except Exception as e:
            app.update_log(f"\nErreur : {e}")
            app.training_finished()

    def _run_match(self):
        app = self.app
        try:
            app.update_log(
                f"Match : {app.match_games} parties  "
                f"A={app.match_weights_a_name}  B={app.match_weights_b_name}"
            )
            wa = wb = draws = 0
            for gn in range(1, app.match_games + 1):
                if not self.running:
                    break
                while self.paused and self.running:
                    time.sleep(0.1)
                if not self.running:
                    break
                app.update_log(f"\nPartie {gn}...")
                if gn % 2 == 1:
                    r = self._play_game(app.match_weights_a, app.match_weights_b)
                    if r == 1:
                        wa += 1
                        app.update_log("  A gagne (Blancs)")
                    elif r == -1:
                        wb += 1
                        app.update_log("  B gagne (Noirs)")
                    else:
                        draws += 1
                        app.update_log("  Nulle")
                else:
                    r = self._play_game(app.match_weights_b, app.match_weights_a)
                    if r == 1:
                        wb += 1
                        app.update_log("  B gagne (Blancs)")
                    elif r == -1:
                        wa += 1
                        app.update_log("  A gagne (Noirs)")
                    else:
                        draws += 1
                        app.update_log("  Nulle")
                app.update_log(f"  Score A={wa} B={wb} N={draws}")
                app.update_progress(gn, app.match_games)
            app.update_log(f"\nFINAL  A:{wa}  B:{wb}  Nulles:{draws}")
            if wa > wb:
                app.update_log(f"{app.match_weights_a_name} gagne !")
            elif wb > wa:
                app.update_log(f"{app.match_weights_b_name} gagne !")
            else:
                app.update_log("Match nul !")
            app.training_finished()
        except Exception as e:
            app.update_log(f"\nErreur : {e}")
            app.training_finished()

    def _mutate(self, w, step):
        """
        Mutation intelligente :
        - Choisit un groupe de parametres (phase, pieces, pions...)
        - Mute 1 a 3 parametres du groupe avec amplitude variable
        - Respecte les bornes WEIGHT_BOUNDS
        """
        nw = dict(w)

        # Choisir un groupe aleatoire
        group_name = random.choice(list(PARAM_GROUPS.keys()))
        params = PARAM_GROUPS[group_name]

        # Nombre de parametres a muter dans ce groupe (1 a 3)
        n_mut = random.randint(1, min(3, len(params)))
        keys  = random.sample(params, n_mut)

        for k in keys:
            lo, hi = WEIGHT_BOUNDS.get(k, (-1e9, 1e9))
            # Amplitude proportionnelle a l'echelle du parametre
            scale = (hi - lo)
            delta = random.choice([-1, 1]) * random.uniform(0.02, 0.15) * scale * (step / 5.0)
            nw[k] = max(lo, min(hi, float(nw[k]) + delta))

        return nw

    def _eval_match(self, best, cand):
        wins = draws = losses = 0
        for i in range(self.app.games_per_eval):
            if not self.running:
                break
            if i % 2 == 0:
                r = self._play_game(cand, best)
                if r == 1:   wins   += 1
                elif r == 0: draws  += 1
                else:         losses += 1
            else:
                r = self._play_game(best, cand)
                if r == -1:  wins   += 1
                elif r == 0: draws  += 1
                else:         losses += 1
        total = wins + draws + losses
        wr = (wins + 0.5 * draws) / total if total > 0 else 0.5
        return wr, {"wins": wins, "draws": draws, "losses": losses}

    def _play_game(self, ww, wb):
        state = GameState(board=initial_board())
        for _ in range(self.app.max_plies):
            b = state.get_board()
            if b.is_game_over():
                break
            weights = ww if state.turn == 1 else wb
            # Injecter les poids actifs pour que evaluate_board les utilise
            set_active_weights(weights)
            res = choose_best_move_timed(
                b,
                movetime_ms=self.app.movetime_ms,
                max_depth=self.app.search_depth,
                weights=weights,
            )
            if res.move is None:
                break
            apply_move_inplace(state, res.move)
        b = state.get_board()
        if b.is_checkmate():
            return -1 if b.turn == chess.WHITE else 1
        return 0

    def stop(self):   self.running = False
    def pause(self):  self.paused  = True
    def resume(self): self.paused  = False


class TrainingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Entrainement IA - python-chess")
        self.root.geometry("1000x700")

        self.training_thread   = None
        self.is_training       = False
        self.is_paused         = False
        self.current_mode      = None
        self.current_generation = 0
        self.best_weights      = DEFAULT_WEIGHTS.copy()

        self.max_iterations  = 50
        self.games_per_eval  = 10
        self.movetime_ms     = 50
        self.search_depth    = 2
        self.max_plies       = 160
        self.mutation_step   = 3
        self.accept_margin   = 0.02

        self.match_games          = 20
        self.match_weights_a      = DEFAULT_WEIGHTS.copy()
        self.match_weights_b      = DEFAULT_WEIGHTS.copy()
        self.match_weights_a_name = "Poids A"
        self.match_weights_b_name = "Poids B"

        self.training_history = []
        self._load_current_state()
        self._build_interface()

    def _load_current_state(self):
        ensure_defaults()
        self.current_generation = latest_generation_index()
        try:
            self.best_weights = load_gen(gen_path(self.current_generation))
        except Exception:
            self.best_weights = DEFAULT_WEIGHTS.copy()

    def _build_interface(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=5, pady=5)
        t1 = ttk.Frame(nb); nb.add(t1, text="Entrainement")
        t2 = ttk.Frame(nb); nb.add(t2, text="Match")
        t3 = ttk.Frame(nb); nb.add(t3, text="Statistiques")
        self._build_training_tab(t1)
        self._build_match_tab(t2)
        self._build_stats_tab(t3)

    def _build_training_tab(self, parent):
        left = ttk.LabelFrame(parent, text="Configuration", padding=10)
        left.pack(side="left", fill="both", padx=5, pady=5)

        ttk.Label(left, text="Generation actuelle:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.gen_label = ttk.Label(
            left,
            text=f"Generation {self.current_generation}",
            font=("Helvetica", 12),
            foreground="blue",
        )
        self.gen_label.pack(anchor="w")

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)

        pf = ttk.Frame(left)
        pf.pack(fill="x")
        rows = [
            ("Iterations max:",   "iterations_var", self.max_iterations, 1,   1000),
            ("Parties/eval:",     "games_eval_var", self.games_per_eval,  2,   100),
            ("Temps/coup (ms):",  "movetime_var",   self.movetime_ms,     10,  1000),
            ("Profondeur:",       "depth_var",       self.search_depth,   1,   6),
            ("Coups max/partie:", "plies_var",       self.max_plies,      50,  500),
            ("Pas de mutation:",  "mutation_var",    self.mutation_step,  1,   20),
        ]
        for i, (lbl, attr, val, mn, mx) in enumerate(rows):
            ttk.Label(pf, text=lbl).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.IntVar(value=val)
            setattr(self, attr, v)
            ttk.Spinbox(pf, from_=mn, to=mx, textvariable=v, width=10).grid(row=i, column=1, pady=2)

        ttk.Label(pf, text="Marge accept:").grid(row=len(rows), column=0, sticky="w", pady=2)
        self.margin_var = tk.DoubleVar(value=self.accept_margin)
        ttk.Spinbox(
            pf, from_=0.0, to=0.2, increment=0.01,
            textvariable=self.margin_var, width=10,
        ).grid(row=len(rows), column=1, pady=2)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)

        cf = ttk.Frame(left)
        cf.pack(fill="x", pady=10)
        self.start_btn = ttk.Button(cf, text="Demarrer",  command=self.start_training)
        self.start_btn.pack(fill="x", pady=2)
        self.pause_btn = ttk.Button(cf, text="Pause",     command=self.pause_training, state="disabled")
        self.pause_btn.pack(fill="x", pady=2)
        self.stop_btn  = ttk.Button(cf, text="Arreter",   command=self.stop_training,  state="disabled")
        self.stop_btn.pack(fill="x", pady=2)

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        prgf = ttk.LabelFrame(right, text="Progression", padding=5)
        prgf.pack(fill="x", pady=5)
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(prgf, variable=self.progress_var, maximum=100).pack(fill="x", pady=2)
        self.progress_label = ttk.Label(prgf, text="0 / 0")
        self.progress_label.pack()

        logf = ttk.LabelFrame(right, text="Journal", padding=5)
        logf.pack(fill="both", expand=True, pady=5)
        sb = ttk.Scrollbar(logf)
        sb.pack(side="right", fill="y")
        self.log_text = tk.Text(logf, height=20, yscrollcommand=sb.set, font=("Courier", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.config(command=self.log_text.yview)

        self.update_log("Pret.")
        self.update_log(f"Generation actuelle : {self.current_generation}")

    def _build_match_tab(self, parent):
        cf = ttk.LabelFrame(parent, text="Configuration du Match", padding=10)
        cf.pack(fill="x", padx=5, pady=5)

        gf = ttk.Frame(cf)
        gf.pack(fill="x", pady=5)
        ttk.Label(gf, text="Nombre de parties:").pack(side="left")
        self.match_games_var = tk.IntVar(value=self.match_games)
        ttk.Spinbox(gf, from_=2, to=200, textvariable=self.match_games_var, width=10).pack(side="left", padx=5)

        ttk.Separator(cf, orient="horizontal").pack(fill="x", pady=10)

        wf = ttk.Frame(cf)
        wf.pack(fill="x", pady=5)
        for side, color in [("a", "Poids A"), ("b", "Poids B")]:
            frm = ttk.LabelFrame(wf, text=color, padding=5)
            frm.pack(side="left", fill="both", expand=True, padx=5)
            lbl = ttk.Label(frm, text="Poids par defaut", font=("Helvetica", 10))
            lbl.pack(pady=5)
            setattr(self, f"weights_{side}_label", lbl)
            ttk.Button(frm, text="Charger",          command=lambda s=side: self.load_weights(s)).pack(fill="x", pady=2)
            ttk.Button(frm, text="Meilleure gen.",   command=lambda s=side: self.use_best_weights(s)).pack(fill="x", pady=2)
            ttk.Button(frm, text="Gen. specifique",  command=lambda s=side: self.use_generation(s)).pack(fill="x", pady=2)

        ttk.Separator(cf, orient="horizontal").pack(fill="x", pady=10)
        self.start_match_btn = ttk.Button(cf, text="Demarrer le Match", command=self.start_match)
        self.start_match_btn.pack(fill="x", pady=5)

        logf = ttk.LabelFrame(parent, text="Journal du Match", padding=5)
        logf.pack(fill="both", expand=True, padx=5, pady=5)
        sb = ttk.Scrollbar(logf)
        sb.pack(side="right", fill="y")
        self.match_log_text = tk.Text(logf, height=15, yscrollcommand=sb.set, font=("Courier", 9))
        self.match_log_text.pack(side="left", fill="both", expand=True)
        sb.config(command=self.match_log_text.yview)

    def _build_stats_tab(self, parent):
        ttk.Label(parent, text="Statistiques", font=("Helvetica", 14, "bold")).pack(pady=10)
        sf = ttk.Frame(parent)
        sf.pack(fill="both", expand=True, padx=10, pady=10)
        sb = ttk.Scrollbar(sf)
        sb.pack(side="right", fill="y")
        self.stats_text = tk.Text(sf, yscrollcommand=sb.set, font=("Courier", 10))
        self.stats_text.pack(side="left", fill="both", expand=True)
        sb.config(command=self.stats_text.yview)
        self.update_stats_display()

    def start_training(self):
        if self.is_training:
            return
        self.max_iterations = int(self.iterations_var.get())
        self.games_per_eval = int(self.games_eval_var.get())
        self.movetime_ms    = int(self.movetime_var.get())
        self.search_depth   = int(self.depth_var.get())
        self.max_plies      = int(self.plies_var.get())
        self.mutation_step  = int(self.mutation_var.get())
        self.accept_margin  = float(self.margin_var.get())

        self.is_training  = True
        self.current_mode = "training"
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")

        self.update_log(f"\n{'='*40}\nENTRAINEMENT\n{'='*40}")
        self.training_thread = TrainingThread(self, "training")
        self.training_thread.start()

    def start_match(self):
        if self.is_training:
            return
        self.match_games = int(self.match_games_var.get())
        self.is_training  = True
        self.current_mode = "match"
        self.start_match_btn.config(state="disabled")
        self.match_log_text.delete(1.0, tk.END)
        self.training_thread = TrainingThread(self, "match")
        self.training_thread.start()

    def pause_training(self):
        if not self.training_thread:
            return
        if self.is_paused:
            self.training_thread.resume()
            self.pause_btn.config(text="Pause")
            self.is_paused = False
        else:
            self.training_thread.pause()
            self.pause_btn.config(text="Reprendre")
            self.is_paused = True

    def stop_training(self):
        if self.training_thread:
            self.training_thread.stop()

    def training_finished(self):
        self.is_training = False
        self.is_paused   = False
        self.root.after(0, self._finish_ui)

    def _finish_ui(self):
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.start_match_btn.config(state="normal")
        self.gen_label.config(text=f"Generation {self.current_generation}")
        self.update_stats_display()

    def update_log(self, msg):
        def _u():
            w = self.match_log_text if self.current_mode == "match" else self.log_text
            w.insert(tk.END, msg + "\n")
            w.see(tk.END)
        self.root.after(0, _u)

    def update_progress(self, cur, tot):
        def _u():
            self.progress_var.set((cur / tot) * 100 if tot > 0 else 0)
            self.progress_label.config(text=f"{cur} / {tot}")
        self.root.after(0, _u)

    def add_training_stats(self, stats):
        self.training_history.append(stats)

    def update_stats_display(self):
        self.stats_text.delete(1.0, tk.END)
        if not self.training_history:
            self.stats_text.insert(tk.END, "Aucune statistique.\nLancez un entrainement.")
            return
        total = len(self.training_history)
        acc   = sum(1 for s in self.training_history if s["accepted"])
        self.stats_text.insert(
            tk.END,
            f"STATISTIQUES\n{'='*40}\n\n"
            f"Iterations : {total}\n"
            f"Acceptes   : {acc}\n"
            f"Taux       : {acc/total*100:.1f}%\n\n"
            f"{'='*40}\nDERNIERES ITERATIONS\n{'='*40}\n\n"
        )
        for s in self.training_history[-20:]:
            st = "OK" if s["accepted"] else "--"
            self.stats_text.insert(
                tk.END,
                f"#{s['iteration']:3d} Gen{s['generation']:2d} "
                f"WR:{s['winrate']:5.1%} {st} "
                f"({s['wins']}/{s['wins']+s['draws']+s['losses']})\n"
            )

    def load_weights(self, side):
        fn = filedialog.askopenfilename(
            title=f"Charger poids {side.upper()}",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
        )
        if not fn:
            return
        try:
            with open(fn) as f:
                data = json.load(f)
            w    = data.get("weights", data)
            name = os.path.basename(fn)
            setattr(self, f"match_weights_{side}", w)
            setattr(self, f"match_weights_{side}_name", name)
            getattr(self, f"weights_{side}_label").config(text=name)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def use_best_weights(self, side):
        try:
            w    = get_best_weights()
            name = f"Best (gen {self.current_generation})"
            setattr(self, f"match_weights_{side}", w)
            setattr(self, f"match_weights_{side}_name", name)
            getattr(self, f"weights_{side}_label").config(text=name)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def use_generation(self, side):
        win = tk.Toplevel(self.root)
        win.title(f"Generation {side.upper()}")
        win.geometry("300x150")
        ttk.Label(win, text="Numero:").pack(pady=10)
        gv = tk.IntVar(value=0)
        ttk.Spinbox(win, from_=0, to=self.current_generation, textvariable=gv, width=10).pack(pady=5)

        def load():
            try:
                w    = load_gen(gen_path(gv.get()))
                name = f"gen_{gv.get()}"
                setattr(self, f"match_weights_{side}", w)
                setattr(self, f"match_weights_{side}_name", name)
                getattr(self, f"weights_{side}_label").config(text=name)
                win.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

        ttk.Button(win, text="Charger", command=load).pack(pady=10)


def main():
    root = tk.Tk()
    TrainingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()