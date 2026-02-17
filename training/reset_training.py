"""
reset_training.py - Réinitialiser l'entraînement de l'IA
"""
import os
import shutil
from datetime import datetime

def reset_training(backup=True):
    """
    Réinitialise l'entraînement.
    Si backup=True, sauvegarde l'ancien entraînement.
    """
    gen_dir = "generations"
    
    if not os.path.exists(gen_dir):
        print("✅ Rien à réinitialiser (dossier inexistant)")
        return
    
    if backup:
        # Créer une sauvegarde
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"generations_backup_{timestamp}"
        shutil.copytree(gen_dir, backup_dir)
        print(f"💾 Sauvegarde créée: {backup_dir}")
    
    # Supprimer le dossier
    shutil.rmtree(gen_dir)
    print(f"🗑️  Dossier {gen_dir}/ supprimé")
    
    # Recréer avec valeurs par défaut
    from training.weights import ensure_defaults
    ensure_defaults()
    print("✅ Réinitialisation terminée!")
    print("   → weights_gen_0.json recréé avec valeurs par défaut")

if __name__ == "__main__":
    import sys
    
    if "--no-backup" in sys.argv:
        reset_training(backup=False)
    else:
        reset_training(backup=True)