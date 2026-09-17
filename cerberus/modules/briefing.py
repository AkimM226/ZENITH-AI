"""
CERBERUS - Module de Briefing à la Demande
Module 1 de ZENITH-SYSTEM
Section 8.3 & Section 10 du document BRIEFING_CERBERUS_v1.md
"""
from typing import Dict, Any, Optional
from datetime import datetime

from ..database.repository import Repository


class BriefingSynthesizer:
    """Génère une synthèse concise et claire pour Akim à sa demande."""

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()

    def generate_briefing(self) -> Dict[str, Any]:
        """Génère la structure de briefing complète."""
        data = self.repo.get_briefing_data()
        pending_alerts = self.repo.list_pending_alerts()
        pending_drafts = self.repo.list_pending_drafts()
        prospects = self.repo.list_prospects()

        urgent_alerts = [a for a in pending_alerts if a.get("niveau") == "URGENT"]
        standard_alerts = [a for a in pending_alerts if a.get("niveau") != "URGENT"]

        now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Rendu textuel formaté pour affichage console / terminal
        text_lines = [
            f"╔══════════════════════════════════════════════════════════════════╗",
            f"║          CERBERUS V1 — BRIEFING COMMERCIAL DE SUPERVISION       ║",
            f"║          Généré le {now_str:<45} ║",
            f"╚══════════════════════════════════════════════════════════════════╝",
            "",
            "📊 INDICATEURS CLÉS DE PERFORMANCE :",
            f"  • Taux de confiance (validation sans retouche) : {data.get('taux_fiabilite', 100.0)}%",
            f"  • Alertes en attente d'arbitrage             : {data.get('total_alerts', 0)} (dont {data.get('urgent_alerts', 0)} urgentes)",
            f"  • Brouillons en attente de validation        : {data.get('pending_drafts', 0)}",
            f"  • Prospects cibles qualifiés                 : {len(prospects)}",
            ""
        ]

        if urgent_alerts:
            text_lines.append("🚨 ARBITRAGES URGENTS (À TRAITER PRIORITAIREMENT) :")
            for idx, a in enumerate(urgent_alerts, 1):
                contact_info = f"{a.get('contact_nom') or 'Inconnu'} <{a.get('contact_email')}>"
                text_lines.append(f"  [{idx}] Contact : {contact_info}")
                text_lines.append(f"      Motif   : {a.get('motif')}")
                text_lines.append(f"      Reçu    : {a.get('timestamp')}")
            text_lines.append("")

        if standard_alerts:
            text_lines.append("⚠️ ALERTES STANDARDS :")
            for idx, a in enumerate(standard_alerts, 1):
                contact_info = f"{a.get('contact_nom') or 'Inconnu'} <{a.get('contact_email')}>"
                text_lines.append(f"  [{idx}] Contact : {contact_info}")
                text_lines.append(f"      Motif   : {a.get('motif')}")
            text_lines.append("")

        if pending_drafts:
            text_lines.append("📝 BROUILLONS EN ATTENTE DE VALIDATION :")
            for idx, d in enumerate(pending_drafts[:5], 1):
                text_lines.append(f"  [{idx}] Vers : {d.get('email_destinataire')} | Objet : {d.get('email_sujet')}")
                text_lines.append(f"      Motif retenue : {d.get('motif_blocage')}")
            if len(pending_drafts) > 5:
                text_lines.append(f"      ... et {len(pending_drafts) - 5} autre(s) brouillon(s).")
            text_lines.append("")

        text_lines.append("ℹ️  Aucun message n'a été envoyé sans votre accord formel en mode V0.")

        formatted_text = "\n".join(text_lines)

        return {
            "timestamp": now_str,
            "metrics": data,
            "urgent_alerts": urgent_alerts,
            "standard_alerts": standard_alerts,
            "pending_drafts": pending_drafts,
            "prospects_count": len(prospects),
            "formatted_text": formatted_text
        }
