"""
main.py - Point d'entrée.
- Sans argument: lance l'interface Tkinter
- Avec argument "uci": lance le serveur UCI (pour entraînement / lichess-bot / cutechess)
"""

import sys

def main():
    if len(sys.argv) >= 2 and sys.argv[1].lower() == "uci":
        from chess_ai.uci import main as uci_main
        uci_main()
    else:
        import tkinter as tk
        from chess_ai.gui import ChessApp
        root = tk.Tk()
        _ = ChessApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
