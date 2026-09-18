"""
Tests unitaires pour le module VOX (Assistant Vocal Local)
Section 3 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md
"""
import pytest
from pathlib import Path
from cerberus.database.repository import Repository
from cerberus.vox.tools import VoxDataTools
from cerberus.vox.assistant import VoxAssistant


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_vox.db"
    return Repository(db_path=db_file)


def test_vox_oral_briefing_generation(temp_repo):
    """Vérifie que VOX produit un texte de briefing oral fluide et bien formaté."""
    tools = VoxDataTools(repo=temp_repo)
    text = tools.get_oral_briefing()
    assert "Bonjour Akim" in text
    assert "alerte" in text
    assert "brouillon" in text


def test_vox_assistant_intents(temp_repo):
    """Vérifie la détection d'intention (briefing, alertes, brouillons)."""
    tools = VoxDataTools(repo=temp_repo)
    assistant = VoxAssistant(data_tools=tools)

    # 1. Demande de briefing
    r1 = assistant.respond("Donne-moi le briefing complet de la situation")
    assert "Bonjour Akim" in r1

    # 2. Demande d'alertes
    r2 = assistant.respond("Y a-t-il des alertes urgentes en attente ?")
    assert "alerte" in r2.lower()

    # 3. Demande de brouillons
    r3 = assistant.respond("Quels sont les brouillons d'emails à valider ?")
    assert "brouillon" in r3.lower()


def test_vox_strict_confirmation_protocol(temp_repo):
    """
    Verifie le garde-fou inviolable : aucune action ne s execute sans confirmation verbale prealable.
    Force api_key=None pour utiliser le chemin fallback deterministe (independant de Gemini/reseau).
    """
    # Creer un contact et un brouillon
    c = temp_repo.get_or_create_contact("prospect@test.bf", "Moussa Traore")
    draft_id = temp_repo.create_draft(
        contact_id=c["id"],
        email_sujet="Devis Formation Arduino",
        email_destinataire="prospect@test.bf",
        corps_propose="Bonjour, tarif 25000 FCFA.",
        motif_blocage="Mode Calibration V0"
    )

    tools = VoxDataTools(repo=temp_repo)
    # api_key=None : force le chemin fallback regex, independant de la disponibilite Gemini
    assistant = VoxAssistant(data_tools=tools, api_key=None)

    # 1. Akim demande de valider le brouillon
    rep_demande = assistant.respond(f"Valide le brouillon {draft_id}")
    assert f"confirmez-vous explicitement la validation du brouillon numero {draft_id}" in rep_demande.lower()

    # Vérifier que le brouillon N'EST PAS encore validé
    d_avant = temp_repo.list_pending_drafts()
    assert any(d["id"] == draft_id for d in d_avant)

    # 2. Akim refuse / annule
    rep_annule = assistant.respond("Non, annule")
    assert "annul" in rep_annule.lower()

    # Le brouillon est toujours en attente
    assert any(d["id"] == draft_id for d in temp_repo.list_pending_drafts())

    # 3. Nouvelle tentative suivie d'une confirmation verbale positive
    assistant.respond(f"Valide le brouillon {draft_id}")
    rep_confirme = assistant.respond("Oui je confirme")
    assert "valid" in rep_confirme.lower() and "succ" in rep_confirme.lower()

    # Le brouillon n'est plus en attente
    assert not any(d["id"] == draft_id for d in temp_repo.list_pending_drafts())

    # L'action a été journalisée avec la mention "Action initiée via VOX"
    logs = temp_repo.list_decision_logs(limit=5)
    assert any("Action initiée via VOX" in (l.get("details") or "") for l in logs)


def test_vox_short_term_memory_and_relative_resolution(temp_repo):
    """
    Verifie la memoire court terme et la resolution des references relatives :
    'quelles sont les alertes ?' puis 'resous la premiere'. (Section 3.2 et 5 de l Addendum 2)
    Force api_key=None pour garantir un chemin deterministe independant de Gemini.
    """
    # Creer 2 alertes distinctes
    a1_id = temp_repo.create_alert(motif="Negociation hors grille Bobo", contexte_email="Email 1", niveau="URGENT")
    a2_id = temp_repo.create_alert(motif="Demande partenariat non qualifiee", contexte_email="Email 2", niveau="STANDARD")

    tools = VoxDataTools(repo=temp_repo)
    # api_key=None : force le chemin fallback regex pour resolution contextuelle deterministe
    assistant = VoxAssistant(data_tools=tools, api_key=None)

    # Tour 1 : Akim consulte les alertes
    res1 = assistant.interact("Quelles sont les alertes en cours ?")
    assert res1["context_card"] is not None
    assert len(assistant.last_mentioned_alerts) >= 2
    assert assistant.last_mentioned_alerts[0]["id"] == a1_id

    # Tour 2 : Akim fait reference a 'la premiere' sans donner l ID
    res2 = assistant.interact("Resous la premiere")
    assert f"confirmez-vous le classement de l alerte numero {a1_id}" in res2["text"].lower()

    # Tour 3 : Akim confirme verbalement
    res3 = assistant.interact("Oui, confirme")
    assert str(a1_id) in res3["text"] and "alerte" in res3["text"].lower() and ("resolu" in res3["text"].lower() or "résolu" in res3["text"].lower())

    # Vérification en base : a1 est résolue, a2 est toujours active
    pending = temp_repo.list_pending_alerts()
    assert not any(a["id"] == a1_id for a in pending)
    assert any(a["id"] == a2_id for a in pending)


def test_vox_interact_context_card_and_ui_actions(temp_repo):
    """
    Verifie le declenchement des actions d interface (UI) pour l Orbe Desktop (Addendum 2).
    Force api_key=None pour chemin fallback deterministe.
    """
    tools = VoxDataTools(repo=temp_repo)
    # api_key=None : garantit que les UI actions passent par le fallback regex
    assistant = VoxAssistant(data_tools=tools, api_key=None)

    # 1. Mode omniprésent
    r_mini = assistant.interact("Passe en mode omniprésent s'il te plaît")
    assert r_mini["ui_action"] == "minimize"

    # 2. Plein écran
    r_full = assistant.interact("Reviens en plein écran")
    assert r_full["ui_action"] == "restore"

    # 3. Mode classique / tableau de bord
    r_man = assistant.interact("Laisse-moi valider moi-même en mode classique")
    assert r_man["ui_action"] == "open_manual"

    # 4. Fermeture de carte contextuelle
    r_close = assistant.interact("Merci c'est bon, referme les infos")
    assert r_close["ui_action"] == "dismiss_card"
    assert len(assistant.last_mentioned_alerts) == 0


def test_vox_gemini_unavailable_graceful_degradation(temp_repo):
    """
    Addendum 4 : Verifie que l assistant degrade gracieusement si Gemini est indisponible
    (pas de cle API, quota depasse, reseau absent).
    Le fallback regex doit repondre correctement aux intentions basiques.
    """
    tools = VoxDataTools(repo=temp_repo)
    # Forcer client=None pour simuler Gemini indisponible
    assistant = VoxAssistant(data_tools=tools, api_key=None)
    assert assistant.client is None, "Le client Gemini doit etre None sans cle API"

    # 1. Briefing via fallback regex
    r_briefing = assistant.respond("Donne-moi le briefing complet de la situation")
    assert "Bonjour Akim" in r_briefing

    # 2. Alertes via fallback regex
    r_alerts = assistant.respond("Est-ce qu il y a des alertes urgentes ?")
    assert "alerte" in r_alerts.lower()

    # 3. Brouillons via fallback regex
    r_drafts = assistant.respond("Montre-moi les brouillons en attente")
    assert "brouillon" in r_drafts.lower()

    # 4. Action UI via fallback regex
    r_ui = assistant.interact("Passe en mode omnipresent discret")
    assert r_ui["ui_action"] == "minimize"

    # 5. Requete inconnue : reponse de secours propre (pas d exception)
    r_unknown = assistant.respond("blabla incomprehensible xyz")
    assert isinstance(r_unknown, str) and len(r_unknown) > 0
