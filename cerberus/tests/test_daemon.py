"""
Tests unitaires pour le mode continu daemon et la prospection sécurisée
Sections 2.1 et 2.2 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md
"""
import json
import pytest
from cerberus.database.repository import Repository
from cerberus.connectors.gmail_client import MockGmailClient
from cerberus.engine.pipeline import CerberusPipeline
from cerberus.modules.prospection import ProspectionEngine
from cerberus.cli import run_worker_cycle


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_daemon.db"
    return Repository(db_path=db_file)


def test_daemon_worker_cycle(temp_repo):
    """Vérifie qu'un cycle de traitement du daemon s'exécute proprement."""
    client = MockGmailClient()
    client.add_simulated_email(
        sender="client1@test.bf",
        subject="Demande formation Arduino",
        body="Bonjour Akim, quel est le tarif pour 1 personne ?"
    )
    client.add_simulated_email(
        sender="direction@entreprise.bf",
        subject="Projet IA Entreprise",
        body="Bonjour, nous aimerions former notre équipe de 5 personnes."
    )
    pipeline = CerberusPipeline(repo=temp_repo)

    count = run_worker_cycle(temp_repo, client, pipeline)
    assert count == 2

    # Vérifier que les messages ont bien été journalisés
    logs = temp_repo.list_decision_logs()
    assert len(logs) >= 2


def test_prospection_empty_source_safe_abort(temp_repo, tmp_path):
    """Vérifie que la prospection sécurisée refuse d'émettre des messages si aucune source réelle n'est fournie."""
    empty_path = tmp_path / "non_existent.json"
    engine = ProspectionEngine(repo=temp_repo)

    # Sans fichier ni liste, renvoie une liste vide sans rien créer
    batch = engine.generate_prospects_batch(file_path=str(empty_path))
    assert batch == []
    assert len(temp_repo.list_prospects()) == 0


def test_prospection_custom_file_import(temp_repo, tmp_path):
    """Vérifie l'importation propre et le placement en Liste Grise depuis un fichier JSON réel."""
    prospects_data = [
        {
            "nom": "Dr Ouedraogo",
            "organisation": "Centre Médical Bobo",
            "secteur": "Santé",
            "ville": "Bobo-Dioulasso",
            "service_cible": "ia_professionnel",
            "email": "dr.ouedraogo@centre-medical-bobo.bf"
        }
    ]
    file_path = tmp_path / "prospects.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(prospects_data, f)

    engine = ProspectionEngine(repo=temp_repo)
    batch = engine.generate_prospects_batch(file_path=str(file_path))

    assert len(batch) == 1
    assert batch[0]["nom"] == "Dr Ouedraogo"
    assert "fcfa" not in batch[0]["premier_message"].lower()

    # Vérification en base
    prospects_db = temp_repo.list_prospects()
    assert len(prospects_db) == 1
    assert prospects_db[0]["email"] == "dr.ouedraogo@centre-medical-bobo.bf"
