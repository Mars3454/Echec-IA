"""
tools/train_generations.py - Entraînement par générations VS Stockfish (rapide).

✅ Rapide car Stockfish reste ouvert (UCIClient).
✅ L'IA progresse par "générations" de poids (hill-climbing).
✅ L'Elo Stockfish s'ajuste automatiquement pour rester dans la zone d'apprentissage.

Sorties:
- generations/weights_gen_X.json
- generations/best.json
- generations/history.jsonl   (logs)

Usage:
python tools/train_generations.py
"""
from __future__ import annotations
import json, os, random, math, time
from datetime import datetime

from tools.uci_client import UCIClient
from chess_ai.engine import GameState, initial_board, uci_to_move, apply_move_inplace, is_checkmate, is_stalemate
from chess_ai.ai import choose_best_move_timed
from chess_ai.weights import (
    ensure_defaults, latest_generation_index, gen_path,
    save_gen, load_gen, set_best
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def now():
    return datetime.now().isoformat(timespec="seconds")

def result_from_state(state: GameState) -> int:
    # +1 si blancs gagnent, -1 si noirs gagnent, 0 sinon
    if is_stalemate(state):
        return 0
    if is_checkmate(state):
        return -1 if state.turn == 1 else 1
    return 0

def play_game_vs_stockfish(sf: UCIClient, sf_elo: int, sf_movetime: int,
                           our_movetime: int, max_plies: int,
                           our_weights: dict, our_color: int) -> int:
    state = GameState(board=initial_board(), turn=1)
    # config stockfish
    sf.set_strength(sf_elo)
    sf.new_game()

    for ply in range(max_plies):
        if is_checkmate(state) or is_stalemate(state):
            break

        if state.turn == our_color:
            res = choose_best_move_timed(state, movetime_ms=our_movetime, max_depth=6, weights=our_weights)
            if res.move is None:
                break
            uci = state.move_history and ""  # no-op to keep style checkers quiet
            uci = __import__("chess_ai.engine", fromlist=["move_to_uci"]).move_to_uci(res.move)
        else:
            uci = sf.bestmove(state.move_history, movetime_ms=sf_movetime)

        apply_move_inplace(state, uci_to_move(state, uci))

    r = result_from_state(state)
    # score du point de vue de notre couleur
    if r == 0:
        return 0
    if our_color == 1:
        return 1 if r == 1 else -1
    else:
        return 1 if r == -1 else -1

def evaluate_weights(sf: UCIClient, cfg: dict, weights: dict, sf_elo: int) -> dict:
    g = int(cfg["games_per_eval"])
    max_plies = int(cfg["max_game_plies"])
    sf_movetime = int(cfg["movetime_ms"])
    our_movetime = int(cfg["our_movetime_ms"])
    wins=draws=losses=0

    for i in range(g):
        our_color = 1 if (i % 2 == 0) else -1
        s = play_game_vs_stockfish(sf, sf_elo, sf_movetime, our_movetime, max_plies, weights, our_color)
        if s > 0: wins += 1
        elif s < 0: losses += 1
        else: draws += 1

    winrate = (wins + 0.5*draws) / max(1, g)
    return {"wins": wins, "draws": draws, "losses": losses, "games": g, "winrate": winrate}

def mutate_weights(w: dict, step: int) -> dict:
    out = dict(w)
    keys = list(out.keys())
    k = random.choice(keys)
    delta = random.choice([-step, step, -2*step, 2*step])
    out[k] = max(0, int(out[k] + delta))
    return out

def adjust_elo(cfg: dict, current_elo: int, winrate: float) -> int:
    # Objectif: rester proche de 50% (zone d'apprentissage)
    step = int(cfg["elo_step"])
    min_elo = int(cfg["min_elo"])
    max_elo = int(cfg["max_elo"])
    if winrate > 0.65:
        current_elo = min(max_elo, current_elo + step)
    elif winrate < 0.35:
        current_elo = max(min_elo, current_elo - step)
    return current_elo

def append_history(record: dict) -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "generations", "history.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def main():
    cfg = load_config()
    ensure_defaults()

    sf = UCIClient(cfg["stockfish_path"])
    sf.init()

    gen = latest_generation_index()
    best_file = gen_path(gen)
    best_weights = load_gen(best_file)

    sf_elo = int(cfg["start_elo"])
    accept_margin = float(cfg.get("accept_margin", 0.02))
    runs = int(cfg["generations_per_run"])
    step = int(cfg["mutation_step"])

    print("=== Training generations vs Stockfish ===")
    print("Start best:", best_file)
    print("Start Stockfish elo:", sf_elo)

    for it in range(1, runs+1):
        # 1) évalue best actuel
        stats_best = evaluate_weights(sf, cfg, best_weights, sf_elo)

        # 2) candidate = mutation légère
        cand_weights = mutate_weights(best_weights, step=step)
        stats_cand = evaluate_weights(sf, cfg, cand_weights, sf_elo)

        accepted = stats_cand["winrate"] >= (stats_best["winrate"] + accept_margin)

        if accepted:
            gen += 1
            out_file = gen_path(gen)
            save_gen(out_file, gen, cand_weights, name=f"gen_{gen}")
            set_best(out_file)
            best_weights = cand_weights
            best_file = out_file

        # 3) ajuste elo pour rester dans zone d'apprentissage
        sf_elo = adjust_elo(cfg, sf_elo, stats_best["winrate"])

        rec = {
            "time": now(),
            "iter": it,
            "stockfish_elo": sf_elo,
            "best_file": os.path.basename(best_file),
            "best": stats_best,
            "cand": stats_cand,
            "accepted": accepted,
            "mutation_step": step,
            "accept_margin": accept_margin,
        }
        append_history(rec)

        print(f"[{it}/{runs}] Elo={sf_elo} | best WR={stats_best['winrate']:.3f} | cand WR={stats_cand['winrate']:.3f} | accepted={accepted}")

    sf.quit()
    print("✅ Terminé. Meilleure génération:", best_file)

if __name__ == "__main__":
    main()
