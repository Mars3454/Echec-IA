

"""
launch_advanced.py - Lance l'interface avec analyse détaillée en temps réel

Affiche :
- Top 5 meilleurs coups
- Évaluation de chaque coup
- Coup choisi par l'IA
- Statistiques (nœuds, temps, nœuds/sec)
- Barre d'évaluation visuelle
"""

import tkinter as tk
import sys
import os

# Ajouter le chemin du projet
project_path = os.path.dirname(os.path.abspath(__file__))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

from chess_ai.gui import ChessApp

if __name__ == "__main__":
    print("🎮 Lancement de l'interface avec analyse avancée...")
    print()
    print("✨ Fonctionnalités :")
    print("   - 📊 Panneau d'analyse en temps réel")
    print("   - 🎯 Top 5 meilleurs coups affichés")
    print("   - ✓ Coup choisi mis en évidence")
    print("   - 📈 Évaluation de position")
    print("   - ⚡ Statistiques de performance")
    print()
    print("💡 Astuce : Augmentez le délai (800-1500ms) pour bien observer l'analyse")
    print()
    
    root = tk.Tk()
    app = ChessApp(root)
    root.mainloop()