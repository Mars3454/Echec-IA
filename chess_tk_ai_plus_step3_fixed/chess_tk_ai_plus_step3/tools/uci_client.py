"""
tools/uci_client.py - Client UCI persistant (IMPORTANT pour la vitesse).

Pourquoi ?
- Si tu relances Stockfish à chaque coup => ultra lent.
- Ici on garde le même process Stockfish ouvert pendant tout l'entraînement.

Fonctions:
- set_strength(elo)
- bestmove(moves, movetime_ms)
"""
from __future__ import annotations
import subprocess
import time
from typing import Optional, List

class UCIClient:
    def __init__(self, exe_path: str):
        self.exe_path = exe_path
        self.p = subprocess.Popen(
            [exe_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

    def send(self, cmd: str) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(cmd + "\n")
        self.p.stdin.flush()

    def read_line(self, timeout: float = 5.0) -> str:
        assert self.p.stdout is not None
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError("UCI read timeout")
            line = self.p.stdout.readline()
            if line:
                return line.strip()

    def read_until(self, token: str, timeout: float = 10.0) -> None:
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError(f"UCI timeout waiting for {token}")
            line = self.read_line(timeout=timeout)
            if token in line:
                return

    def init(self) -> None:
        self.send("uci")
        self.read_until("uciok", timeout=20)
        self.send("isready")
        self.read_until("readyok", timeout=20)

    def new_game(self) -> None:
        self.send("ucinewgame")
        self.send("isready")
        self.read_until("readyok", timeout=20)

    def set_strength(self, elo: int) -> None:
        # Elo minimum ~1320 pour UCI_Elo sur Stockfish (sinon il ignore).
        # On laisse quand même la valeur, mais si tu veux plus facile,
        # baisse plutôt le movetime ou utilise Skill Level dans une version future.
        self.send("setoption name UCI_LimitStrength value true")
        self.send(f"setoption name UCI_Elo value {int(elo)}")

    def bestmove(self, moves_uci: List[str], movetime_ms: int = 60) -> str:
        if moves_uci:
            self.send("position startpos moves " + " ".join(moves_uci))
        else:
            self.send("position startpos")
        self.send(f"go movetime {int(movetime_ms)}")

        while True:
            line = self.read_line(timeout=30)
            if line.startswith("bestmove"):
                parts = line.split()
                return parts[1] if len(parts) >= 2 else "0000"

    def quit(self) -> None:
        try:
            self.send("quit")
        except Exception:
            pass
        try:
            self.p.terminate()
        except Exception:
            pass
