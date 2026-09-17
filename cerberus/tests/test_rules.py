"""
Tests unitaires pour le moteur de règles déterministe (cerberus/engine/rules.py)
Vérifie la conformité absolue avec BRIEFING_CERBERUS_v1.md
"""
import pytest
from cerberus.engine.rules import RuleEngine
from cerberus.config import STATUS_RED, STATUS_GREY, STATUS_WHITE


@pytest.fixture
def rule_engine():
    return RuleEngine()


def test_alert_keywords_legal(rule_engine):
    """Section 3.2 : Mots-clés juridiques/contractuels doivent déclencher une alerte."""
    content = "Pouvez-vous nous envoyer le contrat pour signature avant le début ?"
    has_alert, reasons, urgency = rule_engine.check_alert_keywords(content)
    assert has_alert is True
    assert urgency == "STANDARD"
    assert any("contrat" in r or "signature" in r for r in reasons)


def test_alert_keywords_urgent(rule_engine):
    """Section 3.2 : Mots-clés urgence/pression doivent déclencher une alerte URGENTE."""
    content = "C'est très urgent, nous devons commencer aujourd'hui même sinon j'annule !"
    has_alert, reasons, urgency = rule_engine.check_alert_keywords(content)
    assert has_alert is True
    assert urgency == "URGENT"
    assert any("urgent" in r or "aujourd'hui même" in r for r in reasons)


def test_alert_keywords_partnership(rule_engine):
    """Section 3.2 : Périmètre étendu (partenariat/exclusivité) déclenche une alerte."""
    content = "Nous proposons un partenariat stratégique avec clause d'exclusivité."
    has_alert, reasons, urgency = rule_engine.check_alert_keywords(content)
    assert has_alert is True
    assert any("partenariat" in r or "exclusivité" in r for r in reasons)


def test_service_consulting_general_rejected(rule_engine):
    """Section 5.3 : Le consulting général n'est pas proposé -> Alerte obligatoire."""
    eval_res = rule_engine.check_service_pricing_rules(service_id="consulting_general")
    assert eval_res["valid"] is False
    assert eval_res["requires_alert"] is True
    assert "Section 5.3" in eval_res["alert_reason"]


def test_arduino_below_floor_price(rule_engine):
    """Section 5.1 : Demande sous 15 000 FCFA pour Arduino -> Alerte, aucune négociation permise."""
    eval_res = rule_engine.check_service_pricing_rules(
        service_id="arduino",
        requested_price=10_000
    )
    assert eval_res["valid"] is False
    assert eval_res["requires_alert"] is True
    assert "plancher" in eval_res["alert_reason"]


def test_arduino_valid_discount(rule_engine):
    """Section 5.1 : Réduction Arduino valide avec critères explicites (grand groupe + sur place)."""
    eval_res = rule_engine.check_service_pricing_rules(
        service_id="arduino",
        participants_count=25,
        criteres_reduction=["grand_groupe", "sur_place"]
    )
    assert eval_res["valid"] is True
    assert eval_res["requires_alert"] is False
    assert eval_res["calculated_price"] >= 15_000
    assert eval_res["calculated_price"] < 30_000


def test_ia_initiation_zero_discount(rule_engine):
    """Section 5.2 : IA Initiation -> Zéro réduction possible, même en groupe."""
    eval_res = rule_engine.check_service_pricing_rules(
        service_id="ia_initiation",
        requested_price=12_000,
        participants_count=15
    )
    assert eval_res["valid"] is False
    assert eval_res["requires_alert"] is True
    assert "strictement aucune réduction" in eval_res["alert_reason"]


def test_ia_pro_mandatory_alert(rule_engine):
    """Section 5.2 : IA Professionnel -> Alerte automatique OBLIGATOIRE et systématique pour validation métier."""
    eval_res = rule_engine.check_service_pricing_rules(
        service_id="ia_professionnel",
        participants_count=5
    )
    assert eval_res["requires_alert"] is True
    assert "validation de maîtrise" in eval_res["alert_reason"]


def test_ia_exceeds_three_sessions(rule_engine):
    """Section 5.2 : Au-delà de 3 séances -> bascule automatique sur-mesure et alerte."""
    eval_res = rule_engine.check_service_pricing_rules(
        service_id="ia_professionnel",
        nb_seances=5
    )
    assert eval_res["valid"] is False
    assert eval_res["requires_alert"] is True
    assert "sur-mesure" in eval_res["alert_reason"]


def test_red_list_never_auto_send(rule_engine):
    """Section 3.3 : Liste rouge (institution) -> JAMAIS d'envoi auto, 100% brouillon."""
    contact = {
        "statut": STATUS_RED,
        "is_institution": 1,
        "is_capital_du_savoir": 0,
        "consecutive_validated_count": 10
    }
    res = rule_engine.evaluate(
        email_content="Bonjour, pouvez-vous nous renseigner sur vos formations ?",
        contact=contact,
        service_id="ia_initiation"
    )
    assert res.can_auto_send is False
    assert res.recommended_action == "BROUILLON"


def test_counter_proposal_limit(rule_engine):
    """Section 3.4 : Maximum 1 contre-proposition en autonomie. La 2e déclenche une alerte."""
    contact = {"statut": STATUS_WHITE, "is_institution": 0}
    res = rule_engine.evaluate(
        email_content="Pouvez-vous faire un effort supplémentaire sur le prix ?",
        contact=contact,
        service_id="ia_dev",
        client_counter_proposals=2
    )
    assert res.is_alert is True
    assert any("Seconde contre-proposition" in r for r in res.alert_reasons)


def test_max_words_blocks_auto_send(rule_engine):
    """Section 3.5 : Réponse > 150 mots part automatiquement en brouillon."""
    contact = {"statut": STATUS_WHITE, "is_institution": 0}
    long_reply = "mot " * 160
    res = rule_engine.evaluate(
        email_content="Informations svp",
        contact=contact,
        service_id="arduino",
        generated_reply=long_reply
    )
    assert res.can_auto_send is False
    assert any("trop longue" in r for r in res.blocking_reasons)
