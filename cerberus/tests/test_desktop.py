"""
Tests unitaires pour la passerelle Desktop PyWebView et la robustesse WebView2
Addendum 3 (Correctif critique blocage Ne répond pas)
"""
import pytest
from unittest.mock import MagicMock
from cerberus.ui.desktop import DesktopBridge, start_server_and_wait_ready


def test_desktop_bridge_not_ready_guard():
    """
    Vérifie la mesure 2.1 : aucun redimensionnement/déplacement n'est tenté
    tant que l'événement loaded de WebView2 n'a pas été reçu (is_ready=False).
    """
    mock_window = MagicMock()
    bridge = DesktopBridge(window=mock_window)

    # 1. Par défaut, la fenêtre n'est pas prête
    assert bridge.is_ready is False

    # 2. Une tentative de set_mode doit refuser immédiatement sans toucher à la fenêtre
    res_mode = bridge.set_mode("omnipresent")
    assert res_mode == "not_ready"
    assert mock_window.resize.call_count == 0
    assert mock_window.move.call_count == 0

    # 3. Une tentative de toggle_mode doit également refuser
    res_toggle = bridge.toggle_mode()
    assert res_toggle == "not_ready"

    # 4. Déclenchement de l'événement loaded par WebView2
    bridge.on_loaded()
    assert bridge.is_ready is True

    # 5. Désormais, set_mode s'exécute en toute sécurité
    res_ready = bridge.set_mode("omnipresent")
    assert res_ready == "omnipresent"
    assert mock_window.resize.call_count == 1
    assert mock_window.move.call_count == 1
