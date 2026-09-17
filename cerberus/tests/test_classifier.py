"""
Tests unitaires pour le classificateur d'intention (cerberus/engine/classifier.py)
Section 4 du document BRIEFING_CERBERUS_v1.md
"""
import pytest
from cerberus.engine.classifier import IntentClassifier


@pytest.fixture
def classifier():
    return IntentClassifier()


def test_classify_arduino(classifier):
    content = "Bonjour Akim, nous voulons monter un atelier d'électronique et robotique avec des cartes Arduino et des capteurs."
    res = classifier.classify_rule_based(content, subject="Atelier robotique")
    assert res.service_id == "arduino"
    assert res.service_name == "Formation Arduino"


def test_classify_ia_initiation(classifier):
    content = "Bonjour, j'aimerais découvrir l'IA et apprendre les bases du prompting sur ChatGPT en tant que débutant."
    res = classifier.classify_rule_based(content, subject="Découverte IA")
    assert res.service_id == "ia_initiation"


def test_classify_ia_professionnel(classifier):
    content = "Nous cherchons une formation en IA appliquée à notre métier de comptabilité pour notre équipe de 8 collaborateurs."
    res = classifier.classify_rule_based(content, subject="Formation équipe")
    assert res.service_id == "ia_professionnel"
    assert res.participants_count == 8


def test_classify_ia_dev(classifier):
    content = "Je souhaite me former au vibe coding pour accélérer le développement de sites web et d'applications avec l'IA."
    res = classifier.classify_rule_based(content, subject="Vibe coding")
    assert res.service_id == "ia_dev"


def test_classify_consulting_general(classifier):
    content = "Bonjour, proposez-vous du consulting général et de l'audit stratégique pour restructurer notre entreprise ?"
    res = classifier.classify_rule_based(content, subject="Demande de consulting")
    assert res.service_id == "consulting_general"


def test_detect_tutoiement(classifier):
    content = "Salut Akim, est-ce que tu peux me dire combien coûte ton pack initiation ?"
    res = classifier.classify_rule_based(content, subject="Question tarif")
    assert res.is_tutoiement is True
