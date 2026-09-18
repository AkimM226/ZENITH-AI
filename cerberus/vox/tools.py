"""
CERBERUS VOX - Outils et Données pour l'Assistant Vocal
Section 3.4 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md & Addendum 2
"""
from typing import Dict, Any, List, Optional, Tuple
from cerberus.database.repository import Repository
from cerberus.modules.briefing import BriefingSynthesizer


class VoxDataTools:
    """Fournit à VOX un accès contrôlé aux données métier de CERBERUS."""

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()
        self.briefing_synth = BriefingSynthesizer(self.repo)

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
