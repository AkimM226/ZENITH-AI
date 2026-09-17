"""
CERBERUS - Pipeline d'Orchestration Principal
Module 1 de ZENITH-SYSTEM
"""
from typing import Dict, Any, Optional
from dataclasses import asdict

from cerberus.database.repository import Repository
from .rules import RuleEngine, RuleEvaluationResult
from .classifier import IntentClassifier, ClassificationResult
from .drafter import ResponseDrafter
from cerberus.config import STATUS_RED, STATUS_GREY, STATUS_WHITE


class CerberusPipeline:
    """Orchestre la réception, l'analyse, l'application des règles et la décision pour chaque email."""

    def __init__(
        self,
        repo: Optional[Repository] = None,
        classifier: Optional[IntentClassifier] = None,
        rule_engine: Optional[RuleEngine] = None,
        drafter: Optional[ResponseDrafter] = None,
        email_sender=None
    ):
        self.repo = repo or Repository()
        self.classifier = classifier or IntentClassifier()
        self.rules = rule_engine or RuleEngine()
        self.drafter = drafter or ResponseDrafter()
        self.email_sender = email_sender  # Client Gmail optionnel

    def process_incoming_email(
        self,
        sender_email: str,
        subject: str,
        content: str,
        sender_name: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Traite un email entrant de bout en bout avec traçabilité intégrale.
        """
        # 1. Résolution ou création du contact dans la mémoire persistante
        contact = self.repo.get_or_create_contact(
            email=sender_email,
            nom=sender_name
        )

        # 2. Classification d'intention
        classification: ClassificationResult = self.classifier.classify(content, subject)

        # 3. Pré-évaluation déterministe (sans le corps généré)
        client_counter_props = contact.get("counter_proposal_count", 0)
        # Si un prix est demandé explicitement, incrémenter le suivi de contre-proposition
        if classification.detected_price_demand:
            client_counter_props += 1

        pre_eval = self.rules.evaluate(
            email_content=f"{subject} {content}",
            contact=contact,
            service_id=classification.service_id,
            client_counter_proposals=client_counter_props,
            detected_price_demand=classification.detected_price_demand,
            participants_count=classification.participants_count,
            nb_seances=classification.nb_seances,
            criteres_reduction=classification.criteres_reduction,
            proposes_date_or_schedule=classification.proposes_date
        )

        # 4. Génération de la réponse proposée
        generated_reply = self.drafter.generate_draft(
            contact=contact,
            incoming_content=content,
            incoming_subject=subject,
            service_id=classification.service_id,
            calculated_price=pre_eval.suggested_price,
            is_tutoiement=classification.is_tutoiement
        )

        # 5. Évaluation finale post-rédaction (contrôle de longueur <150 mots, posture)
        eval_result: RuleEvaluationResult = self.rules.evaluate(
            email_content=f"{subject} {content}",
            contact=contact,
            service_id=classification.service_id,
            generated_reply=generated_reply,
            client_counter_proposals=client_counter_props,
            detected_price_demand=classification.detected_price_demand,
            participants_count=classification.participants_count,
            nb_seances=classification.nb_seances,
            criteres_reduction=classification.criteres_reduction,
            proposes_date_or_schedule=classification.proposes_date
        )

        decision = eval_result.recommended_action
        applied_rules_str = "; ".join(eval_result.applied_rules)

        # 6. Routage de la décision
        alert_id = None
        draft_id = None
        sent_automatically = False

        if decision == "ALERTE":
            motif = " | ".join(eval_result.alert_reasons)
            alert_id = self.repo.create_alert(
                motif=motif,
                contexte_email=f"Sujet: {subject}\nExpéditeur: {sender_email}\nMessage:\n{content}",
                contact_id=contact["id"],
                niveau=eval_result.urgency_level
            )
            # Toujours préparer un brouillon associé pour qu'Akim puisse facilement répondre
            draft_id = self.repo.create_draft(
                contact_id=contact["id"],
                email_sujet=f"Re: {subject}",
                email_destinataire=sender_email,
                corps_propose=generated_reply,
                motif_blocage=f"ALERTE DÉCLENCHÉE: {motif}",
                message_id_source=message_id
            )
            self.repo.log_decision(
                type_action="ALERTE",
                regles_appliquees=eval_result.applied_rules,
                resultat="ALERTE_DECLENCHEE",
                contact_id=contact["id"],
                email_sujet=subject,
                details=f"Alerte #{alert_id} niveau {eval_result.urgency_level} : {motif}"
            )

        elif decision == "BROUILLON":
            motif_blocage = " | ".join(eval_result.blocking_reasons) or "Validation requise"
            draft_id = self.repo.create_draft(
                contact_id=contact["id"],
                email_sujet=f"Re: {subject}",
                email_destinataire=sender_email,
                corps_propose=generated_reply,
                motif_blocage=motif_blocage,
                message_id_source=message_id
            )
            self.repo.log_decision(
                type_action="BROUILLON",
                regles_appliquees=eval_result.applied_rules,
                resultat="MIS_EN_ATTENTE_BROUILLON",
                contact_id=contact["id"],
                email_sujet=subject,
                details=f"Brouillon #{draft_id} généré. Motif : {motif_blocage}"
            )

        elif decision == "ENVOI_AUTO":
            # Si tout est vert (liste blanche, règles strictes validées, mode V0 inactif)
            if self.email_sender:
                try:
                    self.email_sender.send_email(
                        to=sender_email,
                        subject=f"Re: {subject}",
                        body=generated_reply,
                        in_reply_to=message_id
                    )
                    sent_automatically = True
                except Exception as e:
                    # En cas d'erreur de transport, bascule immédiate en alerte de sécurité
                    self.repo.create_alert(
                        motif=f"Échec envoi automatique email : {str(e)}",
                        contexte_email=f"Destinataire: {sender_email}\nSujet: {subject}",
                        contact_id=contact["id"],
                        niveau="URGENT"
                    )
            else:
                sent_automatically = True  # Mode simulation

            self.repo.log_decision(
                type_action="ENVOI_AUTO",
                regles_appliquees=eval_result.applied_rules,
                resultat="ENVOYE",
                contact_id=contact["id"],
                email_sujet=subject,
                details="Réponse envoyée automatiquement dans le respect des règles d'autonomie."
            )

        # 7. Mise à jour de l'historique de la mémoire relationnelle
        hist_entry = f"Email reçu: '{subject}'. Action CERBERUS: {decision}."
        self.repo.update_contact_history(
            contact_id=contact["id"],
            summary_update=hist_entry,
            service_detected=classification.service_id
        )

        return {
            "status": "success",
            "decision": decision,
            "contact": contact,
            "classification": classification.model_dump(),
            "evaluation": {
                "is_alert": eval_result.is_alert,
                "urgency": eval_result.urgency_level,
                "reasons": eval_result.alert_reasons or eval_result.blocking_reasons,
                "suggested_price": eval_result.suggested_price,
                "applied_rules": eval_result.applied_rules
            },
            "generated_reply": generated_reply,
            "alert_id": alert_id,
            "draft_id": draft_id,
            "sent_automatically": sent_automatically
        }
