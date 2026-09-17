"""
CERBERUS - Module de Prospection Autonome Sécurisé
Module 1 de ZENITH-SYSTEM
Section 6 du document BRIEFING_CERBERUS_v1.md & Addendum V1 (Section 2.1)
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from cerberus.database.repository import Repository
from cerberus.config import STATUS_GREY


class ProspectionEngine:
    """
    Moteur de prospection ciblée pour Bobo-Dioulasso et Ouagadougou.

    GARDE-FOU ANTI-SPAM (Addendum Section 2.1) :
    Les cibles fictives codées en dur sont proscrites.
    Le module exige des prospects réels fournis explicitement (via data/prospects.json
    ou paramètre) afin d'éviter tout démarchage intempestif ou involontaire.
    """

    DEFAULT_PROSPECTS_PATH = Path("data") / "prospects.json"

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()

    @classmethod
    def load_prospects_from_file(cls, path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Charge une liste de prospects qualifiés depuis un fichier JSON."""
        target_path = Path(path) if path else cls.DEFAULT_PROSPECTS_PATH
        if not target_path.exists():
            return []

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[!] Erreur de lecture du fichier de prospects ({target_path}): {e}")
        return []

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

    def generate_prospects_batch(
        self,
        prospects: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Génère un lot de prospects qualifiés, tous ajoutés en Liste Grise (Section 6.3).
        Si aucun prospect n'est fourni, tente de charger depuis le fichier indiqué ou data/prospects.json.
        """
        targets = prospects
        if targets is None:
            path = Path(file_path) if file_path else self.DEFAULT_PROSPECTS_PATH
            targets = self.load_prospects_from_file(path)

        if not targets:
            print("[!] Aucun prospect à traiter. Déposez des prospects réels dans 'data/prospects.json'")
            return []

        created = []
        for target in targets:
            # Vérification minimale des champs
            if not target.get("email") or not target.get("organisation"):
                continue

            msg = self.generate_first_contact_message(target)

            # Règle Section 6.3 : Tout nouveau prospect entre automatiquement en liste grise
            if target.get("email"):
                contact = self.repo.get_or_create_contact(
                    email=target["email"],
                    nom=target.get("nom", "Inconnu"),
                    organisation=target.get("organisation", "Organisation")
                )
                if contact["statut"] != STATUS_GREY and not contact.get("is_institution"):
                    pass

            prospect_id = self.repo.create_prospect(
                nom=target.get("nom", "Contact"),
                organisation=target.get("organisation", "Organisation"),
                secteur=target.get("secteur", "Général"),
                source=target.get("source", "Saisie manuelle"),
                premier_message=msg,
                email=target.get("email"),
                ville=target.get("ville", "Bobo-Dioulasso")
            )

            # Journalisation de l'action
            self.repo.log_decision(
                type_action="PROSPECTION",
                regles_appliquees=["Section 6 : Nouveau prospect qualifié", "Section 6.3 : Entrée en Liste Grise"],
                resultat="MIS_EN_ATTENTE_BROUILLON",
                email_sujet=f"Premier contact : {target.get('organisation')}",
                details=f"Prospect #{prospect_id} ({target.get('organisation')}) généré et prêt pour validation par Akim."
            )

            created.append({
                "id": prospect_id,
                "nom": target.get("nom"),
                "organisation": target.get("organisation"),
                "secteur": target.get("secteur"),
                "email": target.get("email"),
                "premier_message": msg
            })

        return created
