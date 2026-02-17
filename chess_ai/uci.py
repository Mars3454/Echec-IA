"""
uci.py - Serveur UCI minimal (suffisant pour lichess-bot / cutechess).
Supporte:
- uci / isready / ucinewgame / quit
- position startpos moves ...
- position fen <fen> moves ...
- go depth N
- go movetime MS   (iterative deepening approx)
Répond par: bestmove <uci>
"""

from __future__ import annotations
import sys
from typing import List, Optional

from chess_ai.engine_chess import *
from chess_ai.ai import *

ENGINE_NAME = "ChessTkAI"
ENGINE_AUTHOR = "Valerie + ChatGPT"

def _parse_position(cmd: str) -> GameState:
    parts = cmd.split()
    # position startpos [moves ...]
    if "startpos" in parts:
        st = GameState(board=initial_board(), turn=1)
        if "moves" in parts:
            idx = parts.index("moves") + 1
            for uci in parts[idx:]:
                mv = uci_to_move(st, uci)
                apply_move_inplace(st, mv)
        return st

    # position fen <fen...> [moves ...]
    if "fen" in parts:
        idx = parts.index("fen") + 1
        # fen = 6 champs (placement turn castling ep half full)
        fen_fields = parts[idx:idx+6]
        fen = " ".join(fen_fields)
        st = fen_to_state(fen)
        if "moves" in parts:
            midx = parts.index("moves") + 1
            for uci in parts[midx:]:
                mv = uci_to_move(st, uci)
                apply_move_inplace(st, mv)
        return st

    raise ValueError("position: format non supporté.")

def uci_loop():
    state = GameState(board=initial_board(), turn=1)

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if line == "":
            continue

        if line == "uci":
            print(f"id name {ENGINE_NAME}")
            print(f"id author {ENGINE_AUTHOR}")
            # options utiles (facultatif)
            print("option name Depth type spin default 3 min 1 max 6")
            print("uciok", flush=True)

        elif line == "isready":
            print("readyok", flush=True)

        elif line == "ucinewgame":
            state = GameState(board=initial_board(), turn=1)

        elif line.startswith("position "):
            try:
                state = _parse_position(line)
            except Exception as e:
                # on ne crashe pas
                print(f"info string position parse error: {e}", flush=True)

        elif line.startswith("go"):
            # defaults
            depth = None
            movetime = None

            parts = line.split()
            if "depth" in parts:
                depth = int(parts[parts.index("depth")+1])
            if "movetime" in parts:
                movetime = int(parts[parts.index("movetime")+1])

            if movetime is not None and (depth is None):
                res = choose_best_move_timed(state, movetime_ms=movetime, max_depth=6)
            else:
                res = choose_best_move(state, depth=depth or 2)

            if res.move is None:
                # pas de coups: protocole UCI veut quand même un bestmove
                print("bestmove 0000", flush=True)
            else:
                from engine_chess import move_to_uci
                print(f"bestmove {move_to_uci(res.move)}", flush=True)

        elif line == "d":
            # debug: renvoie fen
            print(f"info string fen {state_to_fen(state)}", flush=True)

        elif line == "quit":
            break

        # ignorer les autres commandes (setoption, stop, ponderhit...)
        else:
            if line.startswith("setoption"):
                # on accepte mais on ignore (minimal)
                pass

def main():
    uci_loop()

if __name__ == "__main__":
    main()