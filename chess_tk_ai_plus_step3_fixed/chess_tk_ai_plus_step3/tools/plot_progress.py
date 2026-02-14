"""
tools/plot_progress.py - Graph simple de la progression (winrate vs génération).

Usage:
python tools/plot_progress.py
=> génère generations/progress.png
"""
from __future__ import annotations
import json, os
import matplotlib.pyplot as plt

HIST = os.path.join(os.path.dirname(__file__), "..", "generations", "history.jsonl")

def main():
    if not os.path.exists(HIST):
        print("Pas de history.jsonl (lance d'abord train_generations.py).")
        return
    gen=[]; wr=[]
    current=0
    with open(HIST,"r",encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec=json.loads(line)
            # best file name contains gen index
            bf=rec.get("best_file","weights_gen_0.json")
            try:
                g=int(bf.split("_")[-1].split(".")[0])
            except Exception:
                g=current
            gen.append(g)
            wr.append(rec["best"]["winrate"])
            current=g
    if not gen:
        print("history vide.")
        return
    plt.figure()
    plt.plot(gen, wr, marker="o")
    plt.xlabel("Génération (best)")
    plt.ylabel("Winrate vs Stockfish (score)")
    plt.title("Progression IA")
    out=os.path.join(os.path.dirname(__file__), "..", "generations", "progress.png")
    plt.savefig(out, dpi=150)
    print("✅ Graph généré:", out)

if __name__=="__main__":
    main()
