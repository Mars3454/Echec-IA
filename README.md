# Chess Tk AI Plus — Étape 3 (final) : GUI + UCI + entraînement rapide (Stockfish) + générations

Tu as :
- Une IA Minimax + Alpha-Bêta (avec optimisations)
- Un système de **progression** (générations de poids) qui peut tourner toute la nuit
- Entraînement **très rapide** car Stockfish reste ouvert (process persistant)

## 1) Lancer l'interface (jouer contre l'IA)
```bash
python main.py
```

L'IA utilise automatiquement la meilleure génération :
- `generations/best.json` pointe vers le meilleur fichier `weights_gen_X.json`

## 2) Mode UCI (pour cutechess / lichess-bot)
```bash
python main.py uci
```

## 3) Entraîner l'IA contre Stockfish (recommandé)
### 3.1 Configure Stockfish
Ouvre `tools/config.json` et mets ton chemin :
```json
"stockfish_path": "E:\\\\val\\\\ECHEC\\\\chess_tk_ai_plus_step1\\\\stockfish.exe"
```

Réglages importants :
- `start_elo` : force de Stockfish au début (ex: 1400)
- `movetime_ms` : temps par coup de Stockfish (ex: 50)
- `our_movetime_ms` : temps par coup de ton IA (ex: 50)
- `games_per_eval` : nb de parties pour comparer (ex: 60)
- `generations_per_run` : nb de tentatives / run (ex: 50)

### 3.2 Lancer
```bash
python tools/train_generations.py
```

**Où est stocké le “niveau” ?**
- Dans `generations/weights_gen_X.json`
- Et `generations/best.json` indique laquelle est la meilleure.

**Le terminal affiche**:
- winrate “best” vs Stockfish
- winrate “candidate”
- accepted=True/False (si la candidate devient la nouvelle génération)

✅ Sécurité : si une mutation est nulle, elle est rejetée -> ton IA ne peut pas “devenir pire” définitivement.

### Elo auto-ajusté (anti-stagnation)
Le script ajuste automatiquement l'Elo de Stockfish :
- si ton IA gagne trop (>65%) -> Elo augmente
- si ton IA perd trop (<35%) -> Elo baisse
Comme ça, tu peux laisser tourner longtemps sans “bloquer”.

## 4) Entraîner en Self-Play (optionnel)
```bash
python tools/selfplay_train.py
```

## 5) Graph de progression
Après un entraînement vs Stockfish :
```bash
python tools/plot_progress.py
```
=> `generations/progress.png`
