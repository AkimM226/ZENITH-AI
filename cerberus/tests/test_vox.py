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
    Vérifie le garde-fou inviolable : aucune action ne s'exécute sans confirmation verbale préalable.
    """
    # Créer un contact et un brouillon
    c = temp_repo.get_or_create_contact("prospect@test.bf", "Moussa Traoré")
    draft_id = temp_repo.create_draft(
        contact_id=c["id"],
        email_sujet="Devis Formation Arduino",
        email_destinataire="prospect@test.bf",
        corps_propose="Bonjour, tarif 25000 FCFA.",
        motif_blocage="Mode Calibration V0"
    )

    tools = VoxDataTools(repo=temp_repo)
    assistant = VoxAssistant(data_tools=tools)

    # 1. Akim demande de valider le brouillon
    rep_demande = assistant.respond(f"Valide le brouillon {draft_id}")
    assert f"confirmez-vous explicitement la validation du brouillon numéro {draft_id}" in rep_demande.lower()

    # Vérifier que le brouillon N'EST PAS encore validé
    d_avant = temp_repo.list_pending_drafts()
    assert any(d["id"] == draft_id for d in d_avant)

    # 2. Akim refuse / annule
    rep_annule = assistant.respond("Non, annule")
    assert "annulée" in rep_annule.lower()

    # Le brouillon est toujours en attente
    assert any(d["id"] == draft_id for d in temp_repo.list_pending_drafts())

    # 3. Nouvelle tentative suivie d'une confirmation verbale positive
    assistant.respond(f"Valide le brouillon {draft_id}")
    rep_confirme = assistant.respond("Oui je confirme")
    assert "validé avec succès" in rep_confirme.lower()

    # Le brouillon n'est plus en attente
    assert not any(d["id"] == draft_id for d in temp_repo.list_pending_drafts())

    # L'action a été journalisée avec la mention "Action initiée via VOX"
    logs = temp_repo.list_decision_logs(limit=5)
    assert any("Action initiée via VOX" in (l.get("details") or "") for l in logs)
