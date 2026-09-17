"""
Tests d'intégration de bout en bout pour le pipeline CERBERUS (cerberus/engine/pipeline.py)
"""
import pytest
from pathlib import Path
from cerberus.database.repository import Repository
from cerberus.engine.pipeline import CerberusPipeline
from cerberus.modules.prospection import ProspectionEngine
from cerberus.modules.briefing import BriefingSynthesizer
from cerberus.config import STATUS_RED, STATUS_GREY, STATUS_WHITE


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_cerberus.db"
    return Repository(db_path=db_file)


@pytest.fixture
def pipeline(temp_repo):
    return CerberusPipeline(repo=temp_repo)


def test_pipeline_urgent_alert(pipeline, temp_repo):
    """Vérifie qu'un email contenant 'urgent' et 'contrat' déclenche une alerte URGENT en base."""
    res = pipeline.process_incoming_email(
        sender_email="directeur@ecole-bobo.bf",
        sender_name="M. Sanou",
        subject="Demande urgente pour signature de contrat",
        content="C'est urgent, nous devons signer le contrat de formation immédiatement."
    )

    assert res["decision"] == "ALERTE"
    assert res["alert_id"] is not None
    assert res["draft_id"] is not None

    # Vérification en base
    alerts = temp_repo.list_pending_alerts()
    assert len(alerts) == 1
    assert alerts[0]["niveau"] == "URGENT"

    logs = temp_repo.list_decision_logs()
    assert len(logs) >= 1
    assert logs[0]["resultat"] == "ALERTE_DECLENCHEE"


def test_pipeline_institution_red_list(pipeline, temp_repo):
    """Vérifie qu'une institution entre en liste rouge et ne peut jamais recevoir d'envoi auto."""
    res = pipeline.process_incoming_email(
        sender_email="contact@banque-regionale.bf",
        sender_name="Service RH",
        subject="Formation IA",
        content="Bonjour, nous aimerions former notre équipe à l'IA."
    )

    contact = temp_repo.get_contact_by_email("contact@banque-regionale.bf")
    assert contact["statut"] == STATUS_RED
    assert contact["is_institution"] == 1
    assert res["sent_automatically"] is False


def test_pipeline_validation_and_downgrade(pipeline, temp_repo):
    """Vérifie la promotion en confiance sans retouche et la rétrogradation en cas de modification."""
    # 1. Contact ordinaire (entre en liste grise)
    res = pipeline.process_incoming_email(
        sender_email="particulier@gmail.com",
        sender_name="Ibrahim",
        subject="Formation Arduino",
        content="Bonjour Akim, combien coûte la formation Arduino pour moi seul ?"
    )
    draft_id = res["draft_id"]
    contact_id = res["contact"]["id"]

    # 2. Validation 1 sans modification
    temp_repo.validate_draft(draft_id)
    c1 = temp_repo.get_contact_by_id(contact_id)
    assert c1["consecutive_validated_count"] == 1

    # 3. Validation 2 sans modification
    temp_repo.increment_contact_validation(contact_id)
    c2 = temp_repo.get_contact_by_id(contact_id)
    assert c2["consecutive_validated_count"] == 2

    # 4. Modification lourde par Akim -> Rétrogradation à 0
    temp_repo.downgrade_contact(contact_id, "Correction lourde du tarif")
    c3 = temp_repo.get_contact_by_id(contact_id)
    assert c3["consecutive_validated_count"] == 0


def test_prospection_and_briefing(temp_repo):
    """Vérifie la génération autonome de prospects et le briefing à la demande."""
    prosp = ProspectionEngine(repo=temp_repo)
    sample_targets = [
        {"nom": "DG", "organisation": "Banque Test", "secteur": "Finance", "email": "contact@banque-test.bf", "service_cible": "ia_professionnel"},
        {"nom": "Pédagogie", "organisation": "Institut Test", "secteur": "Tech", "email": "pedago@inst-test.bf", "service_cible": "arduino"},
        {"nom": "DSI", "organisation": "PME Test", "secteur": "Agro", "email": "dsi@pme-test.bf", "service_cible": "ia_dev"},
        {"nom": "RH", "organisation": "Clinique Test", "secteur": "Santé", "email": "rh@clinique-test.bf", "service_cible": "ia_initiation"},
    ]
    batch = prosp.generate_prospects_batch(prospects=sample_targets)

    assert len(batch) == 4
    # Tous les messages doivent être sans prix ferme
    for p in batch:
        assert "fcfa" not in p["premier_message"].lower()

    # Vérification du briefing synthétiseur
    synth = BriefingSynthesizer(repo=temp_repo)
    briefing = synth.generate_briefing()
    assert briefing["prospects_count"] == 4
    assert "BRIEFING COMMERCIAL DE SUPERVISION" in briefing["formatted_text"]
