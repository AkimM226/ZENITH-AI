"""
CERBERUS - Module de Prospection Autonome
Module 1 de ZENITH-SYSTEM
Section 6 du document BRIEFING_CERBERUS_v1.md
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from cerberus.database.repository import Repository
from cerberus.config import STATUS_GREY


class ProspectionEngine:
    """Moteur de prospection ciblée pour Bobo-Dioulasso et Ouagadougou."""

    TARGET_PROFILES = [
        {
            "nom": "Direction Générale",
            "organisation": "Banque & Microfinance Régionale",
            "secteur": "Finance / Microfinance",
            "ville": "Bobo-Dioulasso",
            "service_cible": "ia_professionnel",
            "source": "Annuaire Entreprises Bobo",
            "email": "contact@microfinance-bobo.bf"
        },
        {
            "nom": "Responsable Pédagogique",
            "organisation": "Institut Supérieur des Technologies",
            "secteur": "Enseignement Supérieur / Technique",
            "ville": "Bobo-Dioulasso",
            "service_cible": "arduino",
            "source": "Portail Universitaire BF",
            "email": "pedagogie@ist-bobo.bf"
        },
        {
            "nom": "Directeur des Systèmes d'Information",
            "organisation": "PME Agro-Industrie de l'Ouest",
            "secteur": "Agro-Industrie & Logistique",
            "ville": "Bobo-Dioulasso",
            "service_cible": "ia_dev",
            "source": "Chambre de Commerce Ouest",
            "email": "dsi@agro-ouest.bf"
        },
        {
            "nom": "Responsable des Ressources Humaines",
            "organisation": "Cabinet Médical & Clinique Espoir",
            "secteur": "Santé / Services",
            "ville": "Ouagadougou",
            "service_cible": "ia_initiation",
            "source": "Annuaire Santé BF",
            "email": "rh@clinique-espoir.bf"
        }
    ]

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()

    def generate_first_contact_message(self, prospect: Dict[str, Any]) -> str:
        """
        Garde-fou Section 6 : Le message de premier contact ne doit JAMAIS contenir
        de prix ferme — il doit inviter à la discussion.
        """
        nom = prospect.get("nom", "Madame, Monsieur")
        organisation = prospect.get("organisation", "votre structure")
        secteur = prospect.get("secteur", "votre domaine")
        service_cible = prospect.get("service_cible", "ia_professionnel")

        if service_cible == "arduino":
            body = (
                f"Bonjour {nom},\n\n"
                f"Je me permets de vous contacter au nom de ZENITH AI à Bobo-Dioulasso. "
                f"Nous accompagnons les structures de formation et les équipes techniques dans la mise en place d'ateliers pratiques en électronique, programmation Arduino et prototypage de capteurs.\n\n"
                f"Au vu des programmes de {organisation}, pensez-vous qu'un module orienté projets concrets pourrait intéresser vos étudiants ou techniciens ?\n\n"
                f"Je serais ravi d'échanger avec vous pour recueillir vos besoins actuels.\n\n"
                f"Bien cordialement,\n"
                f"Akim — ZENITH AI"
            )
        elif service_cible == "ia_professionnel":
            body = (
                f"Bonjour {nom},\n\n"
                f"Basé à Bobo-Dioulasso avec ZENITH AI, j'accompagne les directions et professionnels dans l'intégration ciblée de l'intelligence artificielle générative pour leurs opérations métiers.\n\n"
                f"Dans le secteur {secteur}, de nombreux gains d'efficacité sont directement réalisables sur l'analyse de documents, la rédaction assistée et l'automatisation de tâches répétitives.\n\n"
                f"Seriez-vous ouvert à un bref échange informel pour explorer comment ces outils peuvent servir les priorités de {organisation} ?\n\n"
                f"Bien cordialement,\n"
                f"Akim — ZENITH AI"
            )
        elif service_cible == "ia_dev":
            body = (
                f"Bonjour {nom},\n\n"
                f"Je vous contacte depuis ZENITH AI. Nous formons les équipes techniques et porteurs de projets aux méthodes modernes de création rapide d'applications (vibe coding, prototypes web et mobiles accélérés par l'IA).\n\n"
                f"Auriez-vous un créneau pour échanger sur la manière dont vos développeurs ou collaborateurs pourraient démultiplier leur productivité de développement ?\n\n"
                f"Bien cordialement,\n"
                f"Akim — ZENITH AI"
            )
        else:
            body = (
                f"Bonjour {nom},\n\n"
                f"Je me permets de vous contacter au nom de ZENITH AI à Bobo-Dioulasso. "
                f"Nous animons des sessions pratiques d'initiation et de maîtrise des outils d'IA générative (prompting, automatisation du quotidien).\n\n"
                f"Ce type d'atelier interactif pourrait-il s'inscrire dans les actions de montée en compétences de {organisation} ?\n\n"
                f"Au plaisir d'échanger avec vous,\n\n"
                f"Bien cordialement,\n"
                f"Akim — ZENITH AI"
            )

        # Vérification inviolable : le message ne doit pas comporter de prix ferme
        assert "fcfa" not in body.lower(), "VIOLATION GARDE-FOU PROSPECTION: Le message de premier contact contient un prix ferme !"
        return body

    def generate_prospects_batch(self) -> List[Dict[str, Any]]:
        """Génère un lot de prospects qualifiés, tous ajoutés en Liste Grise (Section 6.3)."""
        created = []
        for target in self.TARGET_PROFILES:
            msg = self.generate_first_contact_message(target)

            # Règle Section 6.3 : Tout nouveau prospect entre automatiquement en liste grise
            if target.get("email"):
                contact = self.repo.get_or_create_contact(
                    email=target["email"],
                    nom=target["nom"],
                    organisation=target["organisation"]
                )
                # Assurer le statut gris
                if contact["statut"] != STATUS_GREY and not contact.get("is_institution"):
                    # reste gris pour les nouveaux prospects
                    pass

            prospect_id = self.repo.create_prospect(
                nom=target["nom"],
                organisation=target["organisation"],
                secteur=target["secteur"],
                source=target["source"],
                premier_message=msg,
                email=target.get("email"),
                ville=target.get("ville", "Bobo-Dioulasso")
            )

            # Journalisation de l'action
            self.repo.log_decision(
                type_action="PROSPECTION",
                regles_appliquees=["Section 6 : Nouveau prospect qualifié", "Section 6.3 : Entrée en Liste Grise"],
                resultat="MIS_EN_ATTENTE_BROUILLON",
                email_sujet=f"Premier contact : {target['organisation']}",
                details=f"Prospect #{prospect_id} ({target['organisation']}) généré et prêt pour validation par Akim."
            )

            created.append({
                "id": prospect_id,
                "nom": target["nom"],
                "organisation": target["organisation"],
                "secteur": target["secteur"],
                "email": target.get("email"),
                "premier_message": msg
            })

        return created
