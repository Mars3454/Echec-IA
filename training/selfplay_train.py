"""
tools/selfplay_train.py - Entraînement simple en self-play (générations).

Utilité:
- Pas besoin de Stockfish.
- Moins efficace pour progresser vite, mais pratique si tu n'as pas Stockfish.

⚠️ Le principe est le même: mutation + match cand vs best => accept/reject.
"""
from __future__ import annotations
import json, os, random
from datetime import datetime
from chess_ai.engine_chess import *
from chess_ai.ai import *
from training.weights import *

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def now(): return datetime.now().isoformat(timespec="seconds")

def result_from_state(state: GameState) -> int:
    if is_stalemate(state): return 0
    if is_checkmate(state): return -1 if state.turn==1 else 1
    return 0

def play_self_game(weights_w: dict, weights_b: dict, our_movetime: int, max_plies: int) -> int:
    state = GameState(board=initial_board(), turn=1)
    for _ in range(max_plies):
        if is_checkmate(state) or is_stalemate(state): break
        if state.turn==1:
            res=choose_best_move_timed(state, movetime_ms=our_movetime, max_depth=2, weights=weights_w)
        else:
            res=choose_best_move_timed(state, movetime_ms=our_movetime, max_depth=2, weights=weights_b)
        if res.move is None: break
        uci = __import__("engine", fromlist=["move_to_uci"]).move_to_uci(res.move)
        apply_move_inplace(state, uci_to_move(state, uci))
    return result_from_state(state)

def evaluate_match(best: dict, cand: dict, games:int, movetime:int, max_plies:int) -> float:
    # score cand (0..1)
    wins=draws=losses=0
    for i in range(games):
        # alterne couleurs: cand joue blanc une partie sur deux
        if i%2==0:
            r = play_self_game(cand, best, movetime, max_plies)
            # r : +1 si blancs gagnent (cand), -1 si noirs (best)
            if r==1: wins+=1
            elif r==0: draws+=1
            else: losses+=1
        else:
            r = play_self_game(best, cand, movetime, max_plies)
            # ici cand est noir => r=-1 pour win cand
            if r==-1: wins+=1
            elif r==0: draws+=1
            else: losses+=1
    return (wins + 0.5*draws)/games

def mutate_weights(w: dict, step:int) -> dict:
    out=dict(w)
    k=random.choice(list(out.keys()))
    out[k]=max(0, int(out[k] + random.choice([-step,step,-2*step,2*step])))
    return out

def main():
    cfg=load_config()
    ensure_defaults()
    gen=latest_generation_index()
    best_file=gen_path(gen)
    best=load_gen(best_file)

    games=int(cfg.get("games_per_eval",1))
    movetime=int(cfg.get("our_movetime_ms",50))
    max_plies=int(cfg.get("max_game_plies",160))
    step=int(cfg.get("mutation_step",3))
    runs=int(cfg.get("generations_per_run",50))
    margin=float(cfg.get("accept_margin",0.02))

    hist=os.path.join(os.path.dirname(__file__),"..","generations","history_selfplay.jsonl")

    for it in range(1,runs+1):
        cand=mutate_weights(best, step)
        wr=evaluate_match(best, cand, games, movetime, max_plies)
        accepted = wr >= (0.5 + margin)
        if accepted:
            gen += 1
            out=gen_path(gen)
            save_gen(out, gen, cand, name=f"gen_{gen}")
            set_best(out)
            best=cand
            best_file=out
        rec={"time":now(),"iter":it,"best_file":os.path.basename(best_file),"cand_winrate":wr,"accepted":accepted}
        with open(hist,"a",encoding="utf-8") as f:
            f.write(json.dumps(rec,ensure_ascii=False)+"\n")
        print(f"[{it}/{runs}] cand_wr={wr:.3f} accepted={accepted}")

    print("✅ Self-play fini. Best:", best_file)

if __name__=="__main__":
    print(True)
    main()
    
