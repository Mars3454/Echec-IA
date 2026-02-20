"""
commentaire général du fichier : 
Ce fichier fournit une interface graphique Tkinter 
dédiée à l'entraînement de l'IA. Il permet de lancer des sessions 
d'entraînement par évolution (mutation + sélection des meilleurs poids),
 de faire jouer deux jeux de poids l'un contre l'autre en match, 
 et de consulter les statistiques des sessions passées
 L'interface est organisée en trois onglets : Entraînement, 
 Match et Statistiques L'entraînement tourne dans un thread séparé 
 pour ne pas bloquer l'interface graphique
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
    """variables : 
self.app ==	Référence à l'instance TrainingGUI, pour accéder aux paramètres et appeler les mises à jour d'interface
self.mode ==	Mode du thread : "training" (entraînement) ou "match" (match libre)
self.running ==	Booléen indiquant si le thread doit continuer à tourner
self.paused == 	Booléen indiquant si le thread est en pause

    """
    def __init__(self, app, mode): 
        """Constructeur. Initialise le thread avec une référence à 
        l'application, le mode ("training" ou "match"), et 
        les drapeaux running=True et paused=False
          Le thread est créé en mode daemon=True :
          il s'arrête automatiquement si la fenêtre est fermée"""
        
        super().__init__(daemon=True)
        self.app = app
        self.mode = mode
        self.running = True
        self.paused = False

    def run(self):
        """Méthode exécutée au démarrage du thread
        Redirige vers _run_training() ou _run_match() selon le mode choisi"""
        if self.mode == "training":
            self._run_training()
        else:
            self._run_match()

    def _run_training(self):
        """Boucle principale d'entraînement. Pour chaque itération :
        vérifie si le thread doit continuer ou est en pause,
        mute les meilleurs poids avec _mutate,
        évalue le candidat avec _eval_match, 
        accepte ou rejette le candidat selon le winrate,
        sauvegarde la nouvelle génération si acceptée, 
        et met à jour l'interface (log, stats, barre de progression)
        En cas d'exception, affiche l'erreur et signale la fin"""

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

        """Boucle principale de match libre. Fait jouer N parties entre 
        les poids A et B en alternant les couleurs
          (A=blancs sur les parties impaires, A=noirs sur les paires)
        Affiche le score au fil des parties et annonce le vainqueur à la fin"""

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
        """Évalue un candidat contre le champion sur games_per_eval parties, 
        en alternant les couleurs. Calcule le winrate du candidat : 
        (victoires + 0.5 × nulles) / total
        Retourne le winrate et un dictionnaire {wins, draws, losses}"""

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
        """Joue une partie complète entre deux jeux de poids 
        Injecte les poids actifs dans l'évaluateur à chaque coup via
        set_active_weights S'arrête en cas de fin de partie
        ou après max_plies demi-coups. Retourne +1 si les blancs gagnent,
        -1 si les noirs gagnent, 0 pour toute nulle"""

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

    def stop(self):   
        """termine la boucle d'entraînement au prochain tour"""
        self.running = False  

    def pause(self): 
        """suspend la boucle via le while self.paused dans _run_training"""
        self.paused  = True

    def resume(self):
        """relance la boucle"""
        self.paused  = False


class TrainingGUI:
    """variables : 
    self.root ==	Fenêtre principale Tkinter
self.training_thread ==	Instance du TrainingThread en cours, None si aucun
self.is_training ==	Booléen : un entraînement ou un match est-il en cours ?
self.is_paused ==	Booléen : l'entraînement est-il en pause ?
self.current_mode == 	Mode actif : "training" ou "match"
self.current_generation ==	Numéro de la génération actuelle chargée depuis le disque
self.best_weights ==	Dictionnaire des meilleurs poids actuels (champion)
self.max_iterations== 	Nombre d'itérations max pour l'entraînement
self.games_per_eval  ==	Nombre de parties jouées pour évaluer un candidat
self.movetime_ms== 	Temps de réflexion en ms par coup pendant l'entraînement
self.search_depth == 	Profondeur de recherche utilisée pendant les parties d'entraînement
self.max_plies == 	Nombre maximum de demi-coups par partie avant de déclarer nulle
self.mutation_step==	Intensité des mutations (facteur multiplicateur)
self.accept_margin== 	 Marge au-dessus de 50% de winrate pour qu'un candidat soit accepté
self.match_games ==	Nombre de parties pour un match libre
self.match_weights_a ==	Poids du joueur A pour le match
self.match_weights_b ==	Poids du joueur B pour le match
self.match_weights_a_name ==	 Nom affiché pour les poids A
self.match_weights_b_name ==	Nom affiché pour les poids B
self.training_history ==	Liste de dictionnaires stockant les stats de chaque itération
self.gen_label == 	Label affichant la génération actuelle dans l'onglet Entraînement
self.log_text ==	Zone de texte scrollable du journal d'entraînement
self.match_log_text	 ==Zone de texte scrollable du journal de match
self.stats_text ==	Zone de texte scrollable de l'onglet Statistiques
self.progress_var ==	Variable Tkinter liée à la barre de progression (0 à 100)
self.progress_label ==	Label affichant "X / total" à côté de la barre
self.start_btn ==	Bouton "Démarrer" l'entraînement
self.pause_btn ==	Bouton "Pause" / "Reprendre"
self.stop_btn ==	Bouton "Arrêter"
self.start_match_btn ==	Bouton "Démarrer le Match"
self.iterations_var ==	Variable Tkinter du spinbox "Iterations max"
self.games_eval_var == 	Variable Tkinter du spinbox "Parties/eval"
self.movetime_var == 	Variable Tkinter du spinbox "Temps/coup"
self.depth_var ==	Variable Tkinter du spinbox "Profondeur"
self.plies_var== 	Variable Tkinter du spinbox "Coups max/partie"
self.mutation_var ==	Variable Tkinter du spinbox "Pas de mutation"
self.margin_var ==	Variable Tkinter du spinbox "Marge accept"
self.match_games_var ==	Variable Tkinter du spinbox "Nombre de parties" du match
"""

    def __init__(self, root): 
        """Constructeur. Initialise toutes les variables de l'application 
        (génération, poids, paramètres d'entraînement et de match, historique),
          charge l'état actuel depuis le disque avec _load_current_state(), 
        puis construit l'interface avec _build_interface()"""

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
        """Appelle ensure_defaults() pour garantir l'existence des fichiers
          de poids, puis charge l'index de la génération
            la plus récente et les poids correspondants
              En cas d'erreur de lecture, replie sur les poids par défaut""" 
        
        ensure_defaults()
        self.current_generation = latest_generation_index()
        try:
            self.best_weights = load_gen(gen_path(self.current_generation))
        except Exception:
            self.best_weights = DEFAULT_WEIGHTS.copy()

    def _build_interface(self): 
        """Crée un Notebook Tkinter (onglets) avec trois onglets :
          "Entraînement", "Match" et "Statistiques", 
        et délègue la construction de chacun aux méthodes dédiées"""

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=5, pady=5)
        t1 = ttk.Frame(nb); nb.add(t1, text="Entrainement")
        t2 = ttk.Frame(nb); nb.add(t2, text="Match")
        t3 = ttk.Frame(nb); nb.add(t3, text="Statistiques")
        self._build_training_tab(t1)
        self._build_match_tab(t2)
        self._build_stats_tab(t3)

    def _build_training_tab(self, parent):
        """Construit l'onglet Entraînement. Colonne gauche :
          label de génération, spinboxes de configuration
            (itérations, parties, temps, profondeur, coups max, mutation,
              marge), boutons Démarrer/Pause/Arrêter. 
        Colonne droite : barre de progression et zone de journal scrollable"""

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
        """Construit l'onglet Match. Spinbox du nombre de parties, 
        deux blocs "Poids A" et "Poids B" avec trois boutons chacun 
        (Charger depuis fichier, Meilleure gen, Gen. spécifique),
          bouton "Démarrer le Match", et journal scrollable du match"""
        
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
        """Construit l'onglet Statistiques : un simple widget Text scrollable
          et appelle update_stats_display() pour le remplir dès l'ouverture"""
        
          
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
        """Démarre l'entraînement. Lit les valeurs des spinboxes, active les boutons Pause et Stop, 
        désactive Démarrer, crée et lance un TrainingThread en mode "training"""
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
        """Démarre un match libre. Lit le nombre de parties,
        vide le journal de match,
          crée et lance un TrainingThread en mode 'match'"""
        
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
        """Bascule entre pause et reprise 
        Met à jour le texte du bouton Pause et appelle thread.pause() 
        ou thread.resume()"""

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
        """Appelle thread.stop() pour demander l'arrêt de l'entraînement"""
        if self.training_thread:
            self.training_thread.stop()

    def training_finished(self):
        """Appelée par le thread en fin d'exécution. Remet les flags à zéro et 
        programme _finish_ui() dans le thread principal via root.after(0, ...)"""

        self.is_training = False
        self.is_paused   = False
        self.root.after(0, self._finish_ui)

    def _finish_ui(self):
        
        """Remet les boutons dans leur état initial (Démarrer réactivé, Pause et Stop désactivés), 
        met à jour le label de génération et rafraîchit l'onglet statistiques"""

        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.start_match_btn.config(state="normal")
        self.gen_label.config(text=f"Generation {self.current_generation}")
        self.update_stats_display()

    def update_log(self, msg):
        """Ajoute une ligne de texte dans le journal approprié (entraînement ou match selon current_mode)
          Utilise root.after(0, ...) pour s'assurer que la mise à jour se fait dans le thread principal Tkinter 
        Contient la fonction interne _u() qui effectue l'insertion"""

        def _u():
            w = self.match_log_text if self.current_mode == "match" else self.log_text
            w.insert(tk.END, msg + "\n")
            w.see(tk.END)
        self.root.after(0, _u)

    def update_progress(self, cur, tot):
        """Met à jour la barre de progression et son label
        Calcule le pourcentage cur/tot * 100
          Utilise root.after(0, ...) avec la fonction interne _u()"""
        
        def _u():
            self.progress_var.set((cur / tot) * 100 if tot > 0 else 0)
            self.progress_label.config(text=f"{cur} / {tot}")
        self.root.after(0, _u)

    def add_training_stats(self, stats): 
        """Ajoute un dictionnaire de statistiques à training_history.
           Appelée par le thread après chaque itération"""
        self.training_history.append(stats)

    def update_stats_display(self):
        """Reécrit entièrement le contenu de l'onglet Statistiques : résumé global (total itérations, nombre d'acceptations, taux d'acceptation),
          puis les 20 dernières itérations avec leur numéro, génération, winrate et résultat"""
       
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
        """Ouvre un filedialog pour choisir un fichier JSON de poids
          Charge le fichier, extrait les poids, et les assigne au joueur A ou B selon side 
        Met à jour le label correspondant"""

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
        """Charge automatiquement les meilleurs poids actuels 
        (via get_best_weights()) et les assigne au joueur A ou B"""

        try:
            w    = get_best_weights()
            name = f"Best (gen {self.current_generation})"
            setattr(self, f"match_weights_{side}", w)
            setattr(self, f"match_weights_{side}_name", name)
            getattr(self, f"weights_{side}_label").config(text=name)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def use_generation(self, side):
        """Ouvre une petite fenêtre Toplevel avec un spinbox pour choisir
          un numéro de génération Contient la fonction interne load() 
          qui charge les poids de la génération choisie et les assigne au joueur A ou B"""
        
        win = tk.Toplevel(self.root)
        win.title(f"Generation {side.upper()}")
        win.geometry("300x150")
        ttk.Label(win, text="Numero:").pack(pady=10)
        gv = tk.IntVar(value=0)
        ttk.Spinbox(win, from_=0, to=self.current_generation, textvariable=gv, width=10).pack(pady=5)

        def load():
            """Ouvre un filedialog pour choisir un fichier JSON de poids 
            Charge le fichier, extrait les poids, et les assigne au joueur A ou B selon side
            Met à jour le label correspondant"""
            
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