"""
selfplay_train.py - Entraînement en self-play par générations (sans Stockfish).

Principe :
  1. Charger les meilleurs poids actuels (champion)
  2. Muter → candidat
  3. Faire jouer champion vs candidat (N parties, couleurs alternées)
  4. Si candidat gagne suffisamment → nouveau champion sauvegardé
  5. Répéter

Corrections vs ancienne version :
  - Utilise chess.Board directement (plus de GameState intermédiaire)
  - Appelle set_active_weights() pour injecter les poids dans evaluate_board
  - Mutation par groupe (compatible avec les 38 nouveaux paramètres)
  - Amplitude de mutation flottante et proportionnelle à l'échelle du paramètre
  - Import corrigé (plus de référence à l'ancien module "engine")
  - Historique JSONL enrichi (groupe muté, paramètres changés)
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime

import chess

# ── Chemins ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

# ── Imports projet ────────────────────────────────────────────────────────────
from chess_ai.engine_chess import GameState, initial_board, apply_move_inplace
from chess_ai.ai import choose_best_move_timed, set_active_weights
from training.weights import (
    DEFAULT_WEIGHTS, WEIGHT_BOUNDS, PARAM_GROUPS,
    ensure_defaults, latest_generation_index, gen_path,
    load_gen, save_gen, set_best, clamp_weights,
)


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────────
# Mutation intelligente (identique à training_gui.py)
# ─────────────────────────────────────────────────────────────────────────────

def mutate_weights(w: dict, mutation_strength: float = 1.0) -> tuple[dict, str, list]:
    """
    Mute 1 à 3 paramètres d'un groupe aléatoire.

    Returns:
        (nouveaux_poids, nom_du_groupe, liste_des_clés_mutées)
    """
    nw = dict(w)

    group_name = random.choice(list(PARAM_GROUPS.keys()))
    params     = PARAM_GROUPS[group_name]
    n_mut      = random.randint(1, min(3, len(params)))
    keys       = random.sample(params, n_mut)

    for k in keys:
        lo, hi = WEIGHT_BOUNDS.get(k, (-1e9, 1e9))
        scale  = hi - lo
        delta  = random.choice([-1, 1]) * random.uniform(0.02, 0.15) * scale * mutation_strength
        nw[k]  = max(lo, min(hi, float(nw[k]) + delta))

    return clamp_weights(nw), group_name, keys


# ─────────────────────────────────────────────────────────────────────────────
# Partie unique en self-play
# ─────────────────────────────────────────────────────────────────────────────

def play_game(weights_white: dict, weights_black: dict,
              movetime_ms: int, max_plies: int) -> int:
    """
    Joue une partie complète.

    Returns:
        +1 si les blancs gagnent, -1 si les noirs gagnent, 0 pour nulle.
    """
    state = GameState(board=initial_board())

    for _ in range(max_plies):
        b = state.get_board()

        if b.is_game_over():
            break

        # Injecter les poids du joueur actif dans l'évaluateur
        weights = weights_white if state.turn == 1 else weights_black
        set_active_weights(weights)

        res = choose_best_move_timed(
            b,
            movetime_ms=movetime_ms,
            max_depth=3,          # depth fixe pour la vitesse d'entraînement
            weights=weights,
        )

        if res.move is None:
            break

        apply_move_inplace(state, res.move)

    b = state.get_board()

    if b.is_checkmate():
        # Le joueur qui doit jouer est en mat → l'autre a gagné
        return -1 if b.turn == chess.WHITE else 1

    return 0   # pat, 50 coups, matériel insuffisant, limite de plies


# ─────────────────────────────────────────────────────────────────────────────
# Évaluation par match (N parties, couleurs alternées)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_match(best: dict, cand: dict,
                   n_games: int, movetime_ms: int,
                   max_plies: int) -> tuple[float, dict]:
    """
    Fait jouer best vs cand sur n_games parties.
    Les couleurs alternent : cand est blanc sur les parties paires, noir sur les impaires.

    Returns:
        (winrate_candidat, stats_dict)
    """
    wins = draws = losses = 0

    for i in range(n_games):
        if i % 2 == 0:
            # Cand = Blancs, Best = Noirs
            r = play_game(cand, best, movetime_ms, max_plies)
            if   r ==  1: wins   += 1   # blancs (cand) gagnent
            elif r ==  0: draws  += 1
            else:          losses += 1   # noirs (best) gagnent
        else:
            # Best = Blancs, Cand = Noirs
            r = play_game(best, cand, movetime_ms, max_plies)
            if   r == -1: wins   += 1   # noirs (cand) gagnent
            elif r ==  0: draws  += 1
            else:          losses += 1   # blancs (best) gagnent

        total = wins + draws + losses
        print(f"  Partie {total}/{n_games} → "
              f"cand W:{wins} D:{draws} L:{losses} "
              f"({(wins + 0.5*draws)/total:.1%})")

    total = wins + draws + losses
    winrate = (wins + 0.5 * draws) / total if total > 0 else 0.5

    return winrate, {"wins": wins, "draws": draws, "losses": losses}


# ─────────────────────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()

    # Paramètres (avec valeurs par défaut raisonnables)
    n_games           = int(cfg.get("games_per_eval",      10))
    movetime_ms       = int(cfg.get("our_movetime_ms",     100))
    max_plies         = int(cfg.get("max_game_plies",      160))
    runs              = int(cfg.get("generations_per_run", 50))
    accept_margin     = float(cfg.get("accept_margin",     0.02))
    mutation_strength = float(cfg.get("mutation_strength", 1.0))

    # Initialisation
    ensure_defaults()
    gen       = latest_generation_index()
    best_file = gen_path(gen)
    best      = load_gen(best_file)

    hist_path = os.path.join(PROJECT_ROOT, "generations", "history_selfplay.jsonl")
    os.makedirs(os.path.dirname(hist_path), exist_ok=True)

    print(f"🎯 Selfplay training — génération de départ : {gen}")
    print(f"   {n_games} parties/éval | movetime={movetime_ms}ms | runs={runs}")
    print(f"   Paramètres entraînables : {len(best)}")
    print()

    for it in range(1, runs + 1):
        print(f"━━━ Itération {it}/{runs} (gen actuelle : {gen}) ━━━")

        # Mutation
        cand, group, mutated_keys = mutate_weights(best, mutation_strength)
        print(f"  Groupe muté : {group} → {mutated_keys}")

        # Afficher les deltas
        for k in mutated_keys:
            print(f"    {k}: {best[k]:.4f} → {cand[k]:.4f} "
                  f"(Δ={cand[k]-best[k]:+.4f})")

        # Match
        winrate, stats = evaluate_match(cand, best, n_games, movetime_ms, max_plies)

        accepted = winrate >= (0.5 + accept_margin)

        if accepted:
            gen      += 1
            out_path  = gen_path(gen)
            save_gen(out_path, gen, cand, name=f"gen_{gen}")
            set_best(out_path)
            best      = cand
            best_file = out_path
            print(f"  ✅ ACCEPTÉ  WR={winrate:.1%} → sauvegardé gen_{gen}")
        else:
            print(f"  ❌ Rejeté   WR={winrate:.1%} (seuil={0.5+accept_margin:.1%})")

        # Historique JSONL
        record = {
            "time":         now(),
            "iteration":    it,
            "generation":   gen,
            "best_file":    os.path.basename(best_file),
            "winrate":      round(winrate, 4),
            "accepted":     accepted,
            "group":        group,
            "mutated_keys": mutated_keys,
            "deltas":       {k: round(cand[k] - best.get(k, 0), 4) for k in mutated_keys},
            **stats,
        }
        with open(hist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print()

    print(f"✅ Selfplay terminé. Meilleure génération : gen_{gen}")
    print(f"   Fichier : {best_file}")


if __name__ == "__main__":
    main()