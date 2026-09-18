"""
CERBERUS VOX - Outils et Données pour l'Assistant Vocal
Section 3.4 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md & Addendum 2
Addendum 6 : Nouveaux outils pour contexte, suggestions et édition
"""
from typing import Dict, Any, List, Optional, Tuple
from cerberus.database.repository import Repository
from cerberus.modules.briefing import BriefingSynthesizer
from cerberus.engine.drafter import ResponseDrafter
from cerberus.engine.rules import RuleEngine
from cerberus.engine.model_cascade import get_model_cascade
from cerberus.config import GEMINI_MODEL


class VoxDataTools:
    """Fournit à VOX un accès contrôlé aux données métier de CERBERUS."""

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()
        self.briefing_synth = BriefingSynthesizer(self.repo)
        self.drafter = ResponseDrafter()
        self.rules = RuleEngine()
        self.model_cascade = get_model_cascade(self.repo)

    def get_oral_briefing(self) -> str:
        """Génère une version concise et adaptée à la voix du briefing quotidien."""
        data = self.briefing_synth.generate_briefing()
        metrics = data.get("metrics", {})
        urgent_alerts = data.get("urgent_alerts", [])
        standard_alerts = data.get("standard_alerts", [])
        all_alerts = urgent_alerts + standard_alerts
        drafts = data.get("pending_drafts", [])
        prospects_count = data.get("prospects_count", 0)

        total_alerts = metrics.get("total_alerts", len(all_alerts))
        total_drafts = metrics.get("pending_drafts", len(drafts))

        lines = [
            f"Bonjour Akim. Voici votre point de situation CERBERUS.",
            f"Aujourd'hui, nous avons {total_alerts} alerte en attente, "
            f"{total_drafts} brouillon à valider, et {prospects_count} prospect enregistré."
        ]

        if urgent_alerts:
            lines.append("Attention prioritaire requise :")
            for a in urgent_alerts[:2]:
                lines.append(f"Alerte urgente pour le motif : {a.get('motif', 'inconnu')}.")
        elif standard_alerts:
            lines.append(f"Une alerte standard est en cours : {standard_alerts[0].get('motif', 'inconnu')}.")

        if drafts:
            first_d = drafts[0]
            lines.append(f"Le premier brouillon en attente concerne l'objet : {first_d.get('email_sujet', 'sans objet')}.")
        else:
            lines.append("Aucun nouveau brouillon en attente.")

        lines.append("Que souhaitez-vous faire ?")
        return " ".join(lines)

    def get_alerts_summary(self) -> str:
        """Résumé oral des alertes en cours."""
        alerts = self.repo.list_pending_alerts()
        if not alerts:
            return "Aucune alerte active à signaler. Tout est sous contrôle, Akim."

        count = len(alerts)
        msg = [f"Vous avez {count} alerte en attente de traitement :"]
        for a in alerts[:3]:
            msg.append(f"Alerte numéro {a['id']}, urgence {a.get('niveau', 'STANDARD')} : {a['motif']}.")
        if count > 3:
            msg.append(f"Et {count - 3} autre(s) alerte(s) consultable(s) sur le tableau de bord.")
        return " ".join(msg)

    def get_drafts_summary(self) -> str:
        """Résumé oral des brouillons en attente de validation."""
        drafts = self.repo.list_pending_drafts()
        if not drafts:
            return "Aucun brouillon en attente de validation actuellement."

        count = len(drafts)
        msg = [f"Il y a {count} brouillon en attente de votre validation :"]
        for d in drafts[:3]:
            contact = d.get("email_destinataire") or "le destinataire"
            msg.append(f"Brouillon numéro {d['id']} pour {contact}, sujet : {d.get('email_sujet', 'Sans sujet')}.")
        return " ".join(msg)

    def get_alerts_data(self) -> Tuple[str, List[Dict[str, Any]]]:
        """Retourne le texte oral et la liste des alertes pour carte contextuelle."""
        alerts = self.repo.list_pending_alerts()
        oral = self.get_alerts_summary()
        return oral, alerts

    def get_drafts_data(self) -> Tuple[str, List[Dict[str, Any]]]:
        """Retourne le texte oral et la liste des brouillons pour carte contextuelle."""
        drafts = self.repo.list_pending_drafts()
        oral = self.get_drafts_summary()
        return oral, drafts

    def get_briefing_full_data(self) -> Tuple[str, Dict[str, Any]]:
        """Retourne le texte oral et l'ensemble des données de briefing."""
        oral = self.get_oral_briefing()
        data = self.briefing_synth.generate_briefing()
        return oral, data

    def execute_draft_validation(self, draft_id: int) -> Dict[str, Any]:
        """
        Valide un brouillon après confirmation explicite.
        Enregistre l'action dans le journal d'audit avec la source VOX.
        """
        try:
            res = self.repo.validate_draft(draft_id)
            if res:
                self.repo.log_decision(
                    type_action="VALIDATION_BROUILLON",
                    regles_appliquees=["Validation explicite via assistant vocal VOX / Orbe"],
                    resultat="BROUILLON_VALIDE_PRET_ENVOI",
                    details=f"Action initiée via VOX : Brouillon #{draft_id} validé verbalement par Akim."
                )
                return {"success": True, "message": f"Le brouillon numéro {draft_id} a été validé avec succès."}
        except Exception as e:
            return {"success": False, "message": f"Impossible de valider le brouillon numéro {draft_id} : {e}"}
        return {"success": False, "message": f"Impossible de valider le brouillon numéro {draft_id}."}

    def execute_alert_resolution(self, alert_id: int) -> Dict[str, Any]:
        """
        Résout une alerte après confirmation explicite.
        """
        try:
            self.repo.resolve_alert(alert_id, notes="Résolue verbalement par Akim via VOX / Orbe")
            self.repo.log_decision(
                type_action="RESOLUTION_ALERTE",
                regles_appliquees=["Résolution explicite via assistant vocal VOX / Orbe"],
                resultat="ALERTE_RESOLUE",
                details=f"Action initiée via VOX : Alerte #{alert_id} classée par Akim."
            )
            return {"success": True, "message": f"L'alerte numéro {alert_id} a été résolue."}
        except Exception as e:
            return {"success": False, "message": f"Erreur lors de la résolution de l'alerte {alert_id} : {e}"}

    # --- ADDENDUM 6: NOUVEAUX OUTILS ---

    def get_email_full_context(self, draft_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Récupère le contexte complet d'un email pour l'Orbe (Addendum 6).
        Retourne le texte oral et les données complètes du brouillon avec le message original.
        """
        draft = self.repo.get_draft_full_context(draft_id)
        if not draft:
            return "Brouillon introuvable.", {}

        contact_nom = draft.get("contact_nom", "Inconnu")
        sujet = draft.get("email_sujet", "Sans sujet")
        texte_original = draft.get("texte_original_client", "Non disponible")
        corps_propose = draft.get("corps_propose", "")

        oral = (
            f"Voici le contexte du message de {contact_nom}. "
            f"Sujet : {sujet}. "
            f"Le client a écrit : {texte_original[:200]}... "
            f"La réponse proposée est : {corps_propose[:150]}..."
        )

        context_data = {
            "type": "email_context",
            "title": f"Contexte Email - {sujet}",
            "contact_nom": contact_nom,
            "contact_email": draft.get("contact_email", ""),
            "sujet": sujet,
            "texte_original": texte_original,
            "corps_propose": corps_propose,
            "draft_id": draft_id
        }

        return oral, context_data

    def suggest_reply_variants(self, draft_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Propose 2-3 variantes de réponse pour un brouillon (Addendum 6).
        Utilise Gemini pour générer des alternatives respectant les règles.
        """
        draft = self.repo.get_draft_full_context(draft_id)
        if not draft:
            return "Brouillon introuvable.", {}

        texte_original = draft.get("texte_original_client", "")
        corps_actuel = draft.get("corps_propose", "")
        sujet = draft.get("email_sujet", "")
        contact = {
            "nom": draft.get("contact_nom", ""),
            "email": draft.get("contact_email", ""),
            "statut": draft.get("contact_statut", "GRISE")
        }

        # Utiliser Gemini directement pour générer des variantes avec cascade
        variants = []
        try:
            if self.drafter.client:
                from google.genai import types

                # Variante 1: Plus directe/concise
                prompt_direct = f"""Génère une variante PLUS DIRECTE et CONCISE de cette réponse :
Sujet : {sujet}
Message client : {texte_original}
Réponse actuelle : {corps_actuel}

Règles : moins de 100 mots, ton direct, Signature Akim — ZENITH AI."""

                def call_variant1(model: str):
                    return self.drafter.client.models.generate_content(
                        model=model,
                        contents=prompt_direct,
                        config=types.GenerateContentConfig(temperature=0.3)
                    )

                result1, _ = self.model_cascade.execute_with_cascade(call_variant1, "suggest_variant1")
                if result1:
                    variant1_text = result1.text.strip()
                    # Valider la variante avec rules.py (Addendum 6)
                    eval1 = self.rules.evaluate(
                        email_content=texte_original,
                        contact=contact,
                        generated_reply=variant1_text
                    )
                    # N'ajouter que si aucune règle bloquante
                    if not eval1.blocking_reasons:
                        variants.append({"style": "Plus directe", "texte": variant1_text})

                # Variante 2: Plus formelle
                prompt_formel = f"""Génère une variante PLUS FORMELLE de cette réponse :
Sujet : {sujet}
Message client : {texte_original}
Réponse actuelle : {corps_actuel}

Règles : vouvoiement, ton professionnel, Signature Akim — ZENITH AI."""

                def call_variant2(model: str):
                    return self.drafter.client.models.generate_content(
                        model=model,
                        contents=prompt_formel,
                        config=types.GenerateContentConfig(temperature=0.3)
                    )

                result2, _ = self.model_cascade.execute_with_cascade(call_variant2, "suggest_variant2")
                if result2:
                    variant2_text = result2.text.strip()
                    # Valider la variante avec rules.py (Addendum 6)
                    eval2 = self.rules.evaluate(
                        email_content=texte_original,
                        contact=contact,
                        generated_reply=variant2_text
                    )
                    # N'ajouter que si aucune règle bloquante
                    if not eval2.blocking_reasons:
                        variants.append({"style": "Plus formelle", "texte": variant2_text})

        except Exception as e:
            # Fallback : utiliser le drafter standard
            try:
                fallback = self.drafter.generate_draft(
                    contact=contact,
                    incoming_content=texte_original,
                    incoming_subject=sujet,
                    is_tutoiement=False
                )
                variants.append({"style": "Standard", "texte": fallback})
            except:
                return f"Erreur lors de la génération des variantes : {e}", {}

        oral = f"Je vous propose {len(variants)} variantes de réponse pour ce brouillon."

        context_data = {
            "type": "suggestions",
            "title": "Variantes de Réponse",
            "draft_id": draft_id,
            "variants": variants[:3]  # Maximum 3 variantes
        }

        return oral, context_data

    def edit_draft(self, draft_id: int, instruction: str) -> Tuple[str, Dict[str, Any]]:
        """
        Modifie un brouillon selon une instruction précise (Addendum 6).
        Le texte modifié passe par les règles de validation avant d'être accepté.
        """
        draft = self.repo.get_draft_full_context(draft_id)
        if not draft:
            return "Brouillon introuvable.", {}

        texte_original = draft.get("texte_original_client", "")
        corps_actuel = draft.get("corps_propose", "")
        sujet = draft.get("email_sujet", "")
        contact = {
            "nom": draft.get("contact_nom", ""),
            "email": draft.get("contact_email", ""),
            "statut": draft.get("contact_statut", "GRISE")
        }

        # Générer une nouvelle version avec l'instruction
        try:
            # Utiliser Gemini avec l'instruction spécifique et cascade
            nouveau_corps = None
            if self.drafter.client:
                from google.genai import types

                prompt_edit = f"""Modifie cette réponse selon l'instruction : {instruction}
Sujet : {sujet}
Message client : {texte_original}
Réponse actuelle : {corps_actuel}

Génère la nouvelle version complète. Respecte les règles : moins de 130 mots, Signature Akim — ZENITH AI."""

                def call_edit(model: str):
                    return self.drafter.client.models.generate_content(
                        model=model,
                        contents=prompt_edit,
                        config=types.GenerateContentConfig(temperature=0.3)
                    )

                response, _ = self.model_cascade.execute_with_cascade(call_edit, "edit_draft")
                if response:
                    nouveau_corps = response.text.strip()

            # Fallback : régénérer sans l'instruction si Gemini échoue
            if not nouveau_corps:
                nouveau_corps = self.drafter.generate_draft(
                    contact=contact,
                    incoming_content=texte_original,
                    incoming_subject=sujet,
                    is_tutoiement=False
                )

            # Vérifier que le nouveau texte respecte les règles (Addendum 6)
            eval_result = self.rules.evaluate(
                email_content=texte_original,
                contact=contact,
                generated_reply=nouveau_corps
            )

            # Si les règles sont violées, refuser la modification
            if eval_result.blocking_reasons:
                return (
                    f"Modification refusée. Règles violées : {' | '.join(eval_result.blocking_reasons)}",
                    {}
                )

            # Appliquer la modification
            self.repo.update_draft_body_temp(draft_id, nouveau_corps)

            oral = f"Brouillon modifié selon votre instruction : {instruction}"

            context_data = {
                "type": "draft_updated",
                "title": "Brouillon Modifié",
                "draft_id": draft_id,
                "instruction": instruction,
                "nouveau_corps": nouveau_corps
            }

            return oral, context_data

        except Exception as e:
            return f"Erreur lors de la modification du brouillon : {e}", {}
