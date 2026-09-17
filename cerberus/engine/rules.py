"""
CERBERUS - Moteur de Règles Déterministe
Module 1 de ZENITH-SYSTEM
Impose les garde-fous stricts du document BRIEFING_CERBERUS_v1.md
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cerberus.config import (
    ALERT_KEYWORDS,
    TARIFS,
    STATUS_RED,
    STATUS_GREY,
    STATUS_WHITE,
    MAX_AUTONOMOUS_WORDS,
    CALIBRATION_MODE
)


@dataclass
class RuleEvaluationResult:
    is_alert: bool = False
    urgency_level: str = "STANDARD"  # "URGENT" ou "STANDARD"
    alert_reasons: List[str] = field(default_factory=list)
    can_auto_send: bool = False
    blocking_reasons: List[str] = field(default_factory=list)
    applied_rules: List[str] = field(default_factory=list)
    recommended_action: str = "BROUILLON"  # "ALERTE", "BROUILLON", "ENVOI_AUTO"
    suggested_price: Optional[int] = None
    service_id: Optional[str] = None


class RuleEngine:
    """Moteur de règles déterministes inviolable."""

    @staticmethod
    def normalize_text(text: str) -> str:
        return text.lower().strip()

    def check_alert_keywords(self, content: str) -> (bool, List[str], str):
        """
        Section 3.2 : Mots-clés déclencheurs d'alerte obligatoire.
        S'appliquent à TOUS les échanges, y compris liste blanche.
        """
        lowered = self.normalize_text(content)
        detected_reasons = []
        urgency = "STANDARD"

        for category, keywords in ALERT_KEYWORDS.items():
            for kw in keywords:
                # Recherche par mot ou expression
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, lowered):
                    detected_reasons.append(f"Mot-clé détecté [{category}]: '{kw}'")
                    if category == "urgence":
                        urgency = "URGENT"

        return (len(detected_reasons) > 0, detected_reasons, urgency)

    def check_service_pricing_rules(
        self,
        service_id: Optional[str],
        requested_price: Optional[int] = None,
        participants_count: int = 1,
        nb_seances: Optional[int] = None,
        criteres_reduction: Optional[List[str]] = None,
        is_institution: bool = False
    ) -> Dict[str, Any]:
        """
        Section 5 : Vérification stricte des grilles tarifaires.
        """
        criteres = criteres_reduction or []
        res = {
            "valid": True,
            "calculated_price": None,
            "requires_alert": False,
            "alert_reason": None,
            "rules_applied": []
        }

        if not service_id:
            return res

        # Service non existant : Consulting général (Section 5.3)
        if service_id == "consulting_general":
            res["valid"] = False
            res["requires_alert"] = True
            res["alert_reason"] = "Demande de 'consulting général' : service explicitement absent de l'offre (Section 5.3)."
            res["rules_applied"].append("Règle 5.3 : Absence offre consulting")
            return res

        # --- 5.1 Formation Arduino ---
        if service_id == "arduino":
            ref = TARIFS["arduino"]["prix_reference"]
            floor = TARIFS["arduino"]["prix_plancher"]

            # Si le client demande un prix sous le plancher absolu
            if requested_price is not None and requested_price < floor:
                res["valid"] = False
                res["requires_alert"] = True
                res["alert_reason"] = f"Demande tarifaire Arduino ({requested_price} FCFA) sous le plancher absolu ({floor} FCFA)."
                res["rules_applied"].append("Règle 5.1 : Prix sous plancher Arduino")
                return res

            # Calcul du tarif selon critères explicites
            price = ref
            if participants_count >= TARIFS["arduino"]["seuil_groupe"] or "grand_groupe" in criteres:
                price = max(floor, price - 10_000)
                res["rules_applied"].append(f"Règle 5.1 : Groupe >= {TARIFS['arduino']['seuil_groupe']} pers")

            if "sur_place" in criteres:
                price = max(floor, price - 3_000)
                res["rules_applied"].append("Règle 5.1 : Formation sur place (pas de déplacement)")

            if "partenaire" in criteres or "client_recurrent" in criteres:
                price = max(floor, price - 2_000)
                res["rules_applied"].append("Règle 5.1 : Client partenaire / récurrent")

            res["calculated_price"] = price
            return res

        # --- 5.2 Formation IA Initiation ---
        if service_id == "ia_initiation":
            price = TARIFS["ia_initiation"]["prix_reference"]
            # Règle stricte : aucune réduction possible, même en groupe
            if requested_price is not None and requested_price < price:
                res["valid"] = False
                res["requires_alert"] = True
                res["alert_reason"] = "Demande de réduction sur IA Initiation : strictement aucune réduction permise (Section 5.2)."
                res["rules_applied"].append("Règle 5.2 : Zéro réduction IA Initiation")
                return res

            res["calculated_price"] = price
            res["rules_applied"].append("Règle 5.2 : Pack IA Initiation tarif ferme 15 000 FCFA")
            return res

        # --- 5.2 Formations IA Pro & IA Dev ---
        if service_id in ("ia_professionnel", "ia_dev"):
            cfg = TARIFS[service_id]

            # Dépassement du nombre de séances incluses (> 3) -> bascule sur-mesure obligatoire
            if nb_seances is not None and nb_seances > cfg["max_seances"]:
                res["valid"] = False
                res["requires_alert"] = True
                res["alert_reason"] = f"Demande de {nb_seances} séances (> 3 incluses) : bascule automatique sur-mesure requise (Section 5.2)."
                res["rules_applied"].append("Règle 5.2 : Dépassement >3 séances IA")
                return res

            # Calcul prix selon seuil institution >= 10 personnes
            if (is_institution or "institution" in criteres) and participants_count >= cfg["seuil_reduction"]:
                price = cfg["prix_reduit"]
                res["rules_applied"].append(f"Règle 5.2 : Tarif réduit institution (>= {cfg['seuil_reduction']} pers)")
            else:
                price = cfg["prix_reference"]
                # Si le client demande un rabais hors de ce seuil
                if requested_price is not None and requested_price < price:
                    res["valid"] = False
                    res["requires_alert"] = True
                    res["alert_reason"] = f"Tentative de négociation hors seuil 10 pers pour {cfg['nom']}."
                    res["rules_applied"].append("Règle 5.2 : Négociation hors seuil")
                    return res

            res["calculated_price"] = price

            # Règle spéciale IA Professionnel : Alerte systématique indépendante du prix pour validation métier
            if service_id == "ia_professionnel":
                res["requires_alert"] = True
                res["alert_reason"] = "Pack Professionnel détecté : Alerte systématique obligatoire pour validation de maîtrise du domaine métier par Akim (Section 5.2)."
                res["rules_applied"].append("Règle 5.2 : Alerte validation métier obligatoire IA Pro")

            return res

        return res

    def evaluate(
        self,
        email_content: str,
        contact: Dict[str, Any],
        service_id: Optional[str] = None,
        generated_reply: Optional[str] = None,
        client_counter_proposals: int = 0,
        detected_price_demand: Optional[int] = None,
        participants_count: int = 1,
        nb_seances: Optional[int] = None,
        criteres_reduction: Optional[List[str]] = None,
        proposes_date_or_schedule: bool = False
    ) -> RuleEvaluationResult:
        """
        Évaluation complète et déterministe d'un message entrant.
        """
        result = RuleEvaluationResult(service_id=service_id)

        # 1. Vérification des mots-clés d'alerte universels (Section 3.2)
        has_alert_kw, kw_reasons, kw_urgency = self.check_alert_keywords(email_content)
        if has_alert_kw:
            result.is_alert = True
            result.urgency_level = kw_urgency
            result.alert_reasons.extend(kw_reasons)
            result.applied_rules.append("Section 3.2 : Déclencheur mot-clé bloquant")

        # 2. Vérification des limites de concession (Section 3.4)
        # Maximum 1 contre-proposition gérée en autonomie. La 2e déclenche une alerte.
        if client_counter_proposals >= 2:
            result.is_alert = True
            result.alert_reasons.append(f"Seconde contre-proposition client ({client_counter_proposals} reçues) : alerte obligatoire (Section 3.4).")
            result.applied_rules.append("Section 3.4 : Limite contre-propositions atteinte (>= 2)")

        # 3. Absence d'engagement sur les dates / planning sans validation (Section 3.4)
        if proposes_date_or_schedule:
            result.is_alert = True
            result.alert_reasons.append("Proposition de date / délai ferme détectée sans validation agenda CHRONOS (Section 3.4).")
            result.applied_rules.append("Section 3.4 : Alerte engagement date")

        # 4. Évaluation des règles de tarification (Section 5)
        pricing_eval = self.check_service_pricing_rules(
            service_id=service_id,
            requested_price=detected_price_demand,
            participants_count=participants_count,
            nb_seances=nb_seances,
            criteres_reduction=criteres_reduction,
            is_institution=bool(contact.get("is_institution", 0))
        )
        result.suggested_price = pricing_eval.get("calculated_price")
        result.applied_rules.extend(pricing_eval.get("rules_applied", []))

        if pricing_eval.get("requires_alert"):
            result.is_alert = True
            result.alert_reasons.append(pricing_eval["alert_reason"])

        # 5. Vérification du statut du contact et des limites d'autonomie (Section 3.3)
        statut = contact.get("statut", STATUS_GREY)
        is_institution = bool(contact.get("is_institution", 0))
        is_capital = bool(contact.get("is_capital_du_savoir", 0))

        if statut == STATUS_RED or is_institution or is_capital:
            result.can_auto_send = False
            result.blocking_reasons.append("Contact en Liste ROUGE (Institution ou Capital du Savoir) : 100% brouillon, aucun envoi automatique permis (Section 3.3).")
            result.applied_rules.append("Section 3.3 : Liste Rouge - Envoi auto interdit")

        elif statut == STATUS_GREY:
            result.can_auto_send = False
            result.blocking_reasons.append("Contact en Liste GRISE (Nouveau prospect / statut par défaut) : validation requise par Akim (Section 3.3).")
            result.applied_rules.append("Section 3.3 : Liste Grise - Brouillon obligatoire")

        elif statut == STATUS_WHITE:
            # En liste blanche, autonomie élargie MAIS JAMAIS sur le prix libre (Section 3.3)
            result.applied_rules.append("Section 3.3 : Contact Liste Blanche")

        # 6. Vérification de la réponse générée (Section 3.5)
        if generated_reply:
            words = generated_reply.strip().split()
            if len(words) > MAX_AUTONOMOUS_WORDS:
                result.can_auto_send = False
                result.blocking_reasons.append(f"Réponse générée trop longue ({len(words)} mots > limite de {MAX_AUTONOMOUS_WORDS} mots) : mise en brouillon automatique (Section 3.5).")
                result.applied_rules.append("Section 3.5 : Dépassement longueur 150 mots")

            # Devis structuré ou planning explicite dans la réponse -> brouillon obligatoire
            lower_reply = generated_reply.lower()
            if "devis :" in lower_reply or "planning :" in lower_reply or "calendrier :" in lower_reply:
                result.can_auto_send = False
                result.blocking_reasons.append("Proposition structurée (devis/planning) dans le corps : mise en brouillon obligatoire (Section 3.5).")
                result.applied_rules.append("Section 3.5 : Proposition structurée en brouillon")

        # 7. Garde-fou V0 : CALIBRATION_MODE (Section 11)
        if CALIBRATION_MODE:
            result.can_auto_send = False
            result.blocking_reasons.append("Mode Calibration V0 actif : zéro envoi automatique pour sécuriser la période de test.")
            result.applied_rules.append("Section 11 : Mode Calibration V0")

        # 8. Règle Méta de Décision Finale (Section 3.1)
        if result.is_alert:
            result.recommended_action = "ALERTE"
            result.can_auto_send = False
        elif not result.can_auto_send or len(result.blocking_reasons) > 0:
            result.recommended_action = "BROUILLON"
        else:
            # Uniquement si liste blanche, aucun mot-clé, aucun dépassement et mode V0 inactif
            result.recommended_action = "ENVOI_AUTO"

        return result
