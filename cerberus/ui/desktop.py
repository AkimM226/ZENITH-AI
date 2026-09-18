"""
CERBERUS DESKTOP — Application Native PyWebView
Correctif Critique Addendum 3 : Stabilité WebView2, Synchronisation UI Thread & Healthcheck Actif
"""
import sys
import time
import urllib.request
import threading
from typing import Optional
import uvicorn

try:
    import webview
except ImportError:
    webview = None


class DesktopBridge:
    """Passerelle API Python exposée au frontend JavaScript de l'Orbe."""

    window: Optional[object]
    is_omnipresent: bool = False
    is_ready: bool = False

    def __init__(self, window: Optional[object] = None):
        self.window = window
        self.is_omnipresent: bool = False
        self.is_ready: bool = False  # Mesure 2.1 : indicateur de disponibilité WebView2
        self._lock = threading.Lock()

    def set_window(self, window: Optional[object]):
        self.window = window

    def on_loaded(self, *args, **kwargs):
        """Déclenché par l'événement window.events.loaded de PyWebView."""
        with self._lock:
            self.is_ready = True
        print("[+] Interface Orbe et contrôleur WebView2 pleinement initialisés (is_ready=True).")

    def toggle_mode(self) -> str:
        """Bascule entre fenêtre complète et mode omniprésent."""
        if not self.is_ready:
            print("[!] Ignoré : WebView2 n'est pas encore prêt (initialisation en cours).")
            return "not_ready"

        if self.is_omnipresent:
            return self.set_mode("fullscreen")
        else:
            return self.set_mode("omnipresent")

    def set_mode(self, mode: str) -> str:
        """
        Configure les dimensions et propriétés de la fenêtre selon l'état choisi.
        Garantit qu'aucune opération n'est exécutée si WebView2 n'est pas prêt (Mesure 2.1).
        """
        if not self.window:
            return "no_window"

        # Mesure 2.1 : Blocage préventif si le contrôleur WebView2 n'a pas fini de charger
        if not self.is_ready:
            print(f"[!] Ignoré : set_mode('{mode}') appelé avant l'événement 'loaded'.")
            return "not_ready"

        with self._lock:
            screens = getattr(webview, "screens", None) if webview is not None else None
            if mode == "omnipresent":
                # Mode Omniprésent : bulle flottante compacte, always-on-top, sans cadre
                self.is_omnipresent = True
                try:
                    self.window.resize(260, 260)
                    self.window.on_top = True
                    if screens:
                        primary = screens[0]
                        target_x = max(0, primary.width - 290)
                        target_y = max(0, primary.height - 310)
                        self.window.move(target_x, target_y)
                except Exception as e:
                    print(f"[!] Avertissement bascule omniprésent : {e}")
                    return "error"
                return "omnipresent"
            else:
                # Mode Fenêtre Complète normale
                self.is_omnipresent = False
                try:
                    self.window.resize(1020, 720)
                    self.window.on_top = False
                    if screens:
                        primary = screens[0]
                        target_x = max(50, (primary.width - 1020) // 2)
                        target_y = max(50, (primary.height - 720) // 2)
                        self.window.move(target_x, target_y)
                except Exception as e:
                    print(f"[!] Avertissement bascule fullscreen : {e}")
                    return "error"
                return "fullscreen"


def start_server_and_wait_ready(host: str = "127.0.0.1", port: int = 8000, timeout: float = 12.0) -> bool:
    """
    Mesure 2.3 : Démarre FastAPI en arrière-plan et effectue un healthcheck HTTP actif
    jusqu'à confirmation de réponse 200 avant de créer la fenêtre WebView.
    """
    config = uvicorn.Config(
        "cerberus.ui.server:app",
        host=host,
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    url = f"http://{host}:{port}/"
    start_time = time.time()
    print(f"[*] Démarrage du serveur local FastAPI sur {url}...")

    # Boucle de vérification active
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cerberus-HealthCheck"})
            with urllib.request.urlopen(req, timeout=0.8) as response:
                if response.status == 200:
                    elapsed = round(time.time() - start_time, 2)
                    print(f"[+] Serveur FastAPI prêt et opérationnel en {elapsed}s.")
                    return True
        except Exception:
            time.sleep(0.15)

    print(f"[!] Délai d'attente dépassé ({timeout}s) pour le démarrage de FastAPI.")
    return False


def run_desktop_app(host: str = "127.0.0.1", port: int = 8000, start_omnipresent: bool = False):
    """Lance l'application native Desktop PyWebView avec synchronisation complète."""
    if not webview:
        print("[!] pywebview n'est pas installé. Lancez 'python -m cerberus ui' pour utiliser un navigateur.")
        return

    # 1. Démarrer et attendre activement la réponse du serveur (Mesure 2.3)
    is_ready = start_server_and_wait_ready(host=host, port=port)
    if not is_ready:
        print("[!] Impossible d'initialiser l'interface Desktop car le serveur local n'a pas répondu.")
        return

    # 2. Instancier le pont API
    bridge = DesktopBridge()
    bridge.is_omnipresent = start_omnipresent

    # 3. Créer la fenêtre native Desktop
    window_url = f"http://{host}:{port}/"
    print(f"[*] Initialisation de la fenêtre WebView2 native...")

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
    if not window:
        print("[!] Erreur : Impossible de créer la fenêtre native PyWebView.")
        return

    bridge.set_window(window)

    # 4. Mesure 2.1 : S'abonner formellement à l'événement 'loaded'
    window.events.loaded += bridge.on_loaded

    # 5. Démarrer la boucle d'événements native
    webview.start(debug=False)
