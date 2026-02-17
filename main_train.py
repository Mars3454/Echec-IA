"""
launch_training.py - Lance l'interface d'entraînement de l'IA

Modes disponibles:
- 🎓 Entraînement: évolution automatique par générations
- ⚔️ Match: comparer deux versions de poids
"""

import tkinter as tk
import sys
import os
from training.training_gui import TrainingGUI
# Ajouter le chemin du projet
project_path = os.path.dirname(os.path.abspath(__file__))
if project_path not in sys.path:
    sys.path.insert(0, project_path)



if __name__ == "__main__":
    print("🎯 Lancement de l'interface d'entraînement...")
    print()
    print("✨ Fonctionnalités :")
    print("   🎓 Mode Entraînement:")
    print("      - Évolution automatique par mutation")
    print("      - Self-play entre candidat et champion")
    print("      - Suivi de la progression en temps réel")
    print()
    print("   ⚔️ Mode Match:")
    print("      - Comparer deux versions de poids")
    print("      - Charger depuis fichiers ou générations")
    print("      - Statistiques détaillées")
    print()
    print("   📊 Statistiques:")
    print("      - Historique complet")
    print("      - Taux d'acceptation")
    print("      - Évolution des performances")
    print()
    
    root = tk.Tk()
    app = TrainingGUI(root)
    root.mainloop()






