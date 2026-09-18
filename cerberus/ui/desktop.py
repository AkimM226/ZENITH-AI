"""
CERBERUS DESKTOP — Application Native PyWebView
Section 2 du document ADDENDUM_2_ORBE_INTERFACE.md
Gère les deux modes d'affichage : Fenêtre Complète et Mode Omniprésent Flottant.
"""
import sys
import time
import threading
import uvicorn
from typing import Optional

try:
    import webview
except ImportError:
    webview = None


class DesktopBridge:
    """Passerelle API Python exposée au frontend JavaScript de l'Orbe."""

    def __init__(self, window=None):
        self.window = window
        self.is_omnipresent = False

    def set_window(self, window):
        self.window = window

    def toggle_mode(self) -> str:
        """Bascule entre fenêtre complète et mode omniprésent."""
        if self.is_omnipresent:
            return self.set_mode("fullscreen")
        else:
            return self.set_mode("omnipresent")

    def set_mode(self, mode: str) -> str:
        """Configure les dimensions et propriétés de la fenêtre selon l'état choisi."""
        if not self.window:
            return "no_window"

        if mode == "omnipresent":
            # Mode Omniprésent : bulle flottante compacte, always-on-top, sans cadre
            self.is_omnipresent = True
            try:
                self.window.resize(260, 260)
                self.window.on_top = True
                # Déplacer vers le coin inférieur droit de l'écran
                screens = webview.screens
                if screens:
                    primary = screens[0]
                    target_x = primary.width - 280
                    target_y = primary.height - 300
                    self.window.move(target_x, target_y)
            except Exception as e:
                print(f"[!] Erreur bascule omniprésent : {e}")
            return "omnipresent"
        else:
            # Mode Fenêtre Complète normale
            self.is_omnipresent = False
            try:
                self.window.resize(1020, 720)
                self.window.on_top = False
                screens = webview.screens
                if screens:
                    primary = screens[0]
                    target_x = max(50, (primary.width - 1020) // 2)
                    target_y = max(50, (primary.height - 720) // 2)
                    self.window.move(target_x, target_y)
            except Exception as e:
                print(f"[!] Erreur bascule fullscreen : {e}")
            return "fullscreen"


def start_server_in_thread(host: str = "127.0.0.1", port: int = 8000):
    """Démarre le serveur FastAPI en tâche de fond pour alimenter PyWebView."""
    config = uvicorn.Config("cerberus.ui.server:app", host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    # Attendre brièvement que le serveur écoute
    time.sleep(1.2)
    return server


def run_desktop_app(host: str = "127.0.0.1", port: int = 8000, start_omnipresent: bool = False):
    """Lance l'application native Desktop PyWebView."""
    if not webview:
        print("[!] pywebview n'est pas installé. Lancez 'python -m cerberus ui' pour utiliser un navigateur standard.")
        return

    # 1. Démarrer le serveur local FastAPI
    print(f"[*] Initialisation du serveur local CERBERUS...")
    start_server_in_thread(host=host, port=port)

    # 2. Créer l'instance de pont API
    bridge = DesktopBridge()

    # 3. Créer la fenêtre native Desktop
    window_url = f"http://{host}:{port}/"
    print(f"[*] Lancement de l'Orbe Desktop native...")

    initial_width = 260 if start_omnipresent else 1020
    initial_height = 260 if start_omnipresent else 720

    window = webview.create_window(
        title="CERBERUS // ZENITH AI",
        url=window_url,
        js_api=bridge,
        width=initial_width,
        height=initial_height,
        resizable=True,
        frameless=start_omnipresent,
        on_top=start_omnipresent,
        background_color="#050811"
    )
    bridge.set_window(window)
    bridge.is_omnipresent = start_omnipresent

    # 4. Lancer la boucle d'événements native
    webview.start(debug=False)
