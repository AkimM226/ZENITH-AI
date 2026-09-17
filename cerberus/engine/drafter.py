"""
CERBERUS - Rédacteur de Réponses et Brouillons
Module 1 de ZENITH-SYSTEM
Respecte les règles culturelles et de ton (Section 3.5)
"""
from typing import Dict, Any, Optional
import re

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from ..config import GEMINI_API_KEY, GEMINI_MODEL, STATUS_RED, STATUS_WHITE, TARIFS


class ResponseDrafter:
    """Génère des réponses respectant strictement la posture d'Akim et ZENITH AI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def draft_fallback(
        self,
        contact: Dict[str, Any],
        incoming_content: str,
        service_id: Optional[str],
        calculated_price: Optional[int],
        is_tutoiement: bool = False
    ) -> str:
        """Générateur de réponse de secours déterministe et conforme aux règles."""
        nom = contact.get("nom", "Madame, Monsieur")
        statut = contact.get("statut", "GRISE")
        is_red = (statut == STATUS_RED)

        # Salutation
        if is_tutoiement and not is_red:
            salutation = f"Bonjour {nom},"
            formule_politesse = "Bien à toi,\nAkim — ZENITH AI"
            pronom = "tu"
        else:
            salutation = f"Bonjour {nom}," if nom != "Madame, Monsieur" else "Bonjour,"
            formule_politesse = "Bien cordialement,\nAkim — ZENITH AI"
            pronom = "vous"

        if service_id == "arduino":
            prix = calculated_price or TARIFS["arduino"]["prix_reference"]
            if pronom == "tu":
                body = (
                    f"{salutation}\n\n"
                    f"Merci pour ton message et ton intérêt pour la formation Arduino et électronique.\n\n"
                    f"Cette session pratique permet de maîtriser les bases du prototypage, des microcontrôleurs et des capteurs. "
                    f"Pour ce format, le tarif est de {prix:,} FCFA par participant.\n\n"
                    f"Quel serait ton niveau actuel et le calendrier envisagé ?\n\n"
                    f"{formule_politesse}"
                )
            else:
                body = (
                    f"{salutation}\n\n"
                    f"Nous vous remercions pour votre intérêt concernant notre formation Arduino et systèmes embarqués.\n\n"
                    f"Ce parcours intensif et pratique aborde la programmation sur microcontrôleurs, le câblage de capteurs et la réalisation de prototypes concrets. "
                    f"Le tarif de référence est de {prix:,} FCFA par participant.\n\n"
                    f"Afin de vous orienter au mieux, pourriez-vous nous préciser le nombre de participants ainsi que vos objectifs ?\n\n"
                    f"{formule_politesse}"
                )

        elif service_id == "ia_initiation":
            prix = TARIFS["ia_initiation"]["prix_reference"]
            format_s = TARIFS["ia_initiation"]["format"]
            if pronom == "tu":
                body = (
                    f"{salutation}\n\n"
                    f"Merci pour ton message ! Le Pack Initiation à l'IA ({format_s}) est idéal pour découvrir le panorama de l'IA générative et maîtriser les techniques de prompting.\n\n"
                    f"Le tarif est fixé à {prix:,} FCFA par participant.\n\n"
                    f"Quand souhaiterais-tu démarrer ?\n\n"
                    f"{formule_politesse}"
                )
            else:
                body = (
                    f"{salutation}\n\n"
                    f"Nous vous remercions pour votre prise de contact.\n\n"
                    f"Notre Pack Initiation à l'IA ({format_s}) a été conçu pour appréhender concrètement l'IA générative et acquérir une méthode rigoureuse de prompting. "
                    f"Ce module est proposé au tarif de {prix:,} FCFA par participant.\n\n"
                    f"Restant à votre disposition pour convenir des modalités,\n\n"
                    f"{formule_politesse}"
                )

        elif service_id == "ia_professionnel":
            prix = calculated_price or TARIFS["ia_professionnel"]["prix_reference"]
            body = (
                f"{salutation}\n\n"
                f"Nous vous remercions pour votre sollicitation relative à notre formation IA Professionnelle.\n\n"
                f"Ce module sur-mesure (jusqu'à 3 séances ciblées) s'adapte spécifiquement aux enjeux et processus de votre activité. "
                f"Le tarif de référence est de {prix:,} FCFA par participant.\n\n"
                f"Je reviens vers vous très prochainement après analyse de votre contexte métier pour affiner le programme.\n\n"
                f"{formule_politesse}"
            )

        elif service_id == "ia_dev":
            prix = calculated_price or TARIFS["ia_dev"]["prix_reference"]
            body = (
                f"{salutation}\n\n"
                f"Merci pour votre intérêt pour notre formation IA Dev (Vibe Coding).\n\n"
                f"Ce programme pratique permet d'accélérer la création d'applications web et mobiles en combinant les outils d'IA les plus performants. "
                f"Le tarif est de {prix:,} FCFA par participant (3 séances incluses).\n\n"
                f"Avez-vous déjà une idée de projet ou d'application que vous souhaiteriez prototyper ?\n\n"
                f"{formule_politesse}"
            )

        elif service_id == "consulting_general":
            body = (
                f"{salutation}\n\n"
                f"Nous accusons bonne réception de votre demande.\n\n"
                f"Nos interventions sont principalement concentrées sur les formations opérationnelles et le développement applicatif. "
                f"Je prends connaissance de votre besoin spécifique et reviendrai vers vous pour voir comment nous pouvons au mieux vous accompagner.\n\n"
                f"{formule_politesse}"
            )

        else:
            body = (
                f"{salutation}\n\n"
                f"Nous vous remercions pour votre message.\n\n"
                f"Nous avons bien noté votre sollicitation et étudions actuellement votre demande afin de vous apporter la réponse la plus adaptée.\n\n"
                f"{formule_politesse}"
            )

        return body.replace(",,", ",")

    def generate_draft(
        self,
        contact: Dict[str, Any],
        incoming_content: str,
        incoming_subject: str,
        service_id: Optional[str] = None,
        calculated_price: Optional[int] = None,
        is_tutoiement: bool = False
    ) -> str:
        """Génère le texte de la réponse, via Gemini si disponible ou via fallback."""
        if not self.client:
            return self.draft_fallback(contact, incoming_content, service_id, calculated_price, is_tutoiement)

        statut = contact.get("statut", "GRISE")
        is_red = (statut == STATUS_RED)
        use_tutoiement = is_tutoiement and not is_red

        system_instruction = f"""Tu es CERBERUS, l'agent commercial personnel d'Akim (ZENITH AI, basé à Bobo-Dioulasso, Burkina Faso).
Tu dois rédiger une réponse d'email professionnelle, chaleureuse et concise.

RÈGLES STRICTES DE POSTURE :
1. {'Tutoie le contact car il a explicitement tutoyé en premier.' if use_tutoiement else 'Vouvoie toujours le contact (règle obligatoire).'}
2. Longueur : STRICTEMENT MOINS DE 130 MOTS. Reste direct, clair et engageant.
3. Ne compare JAMAIS ni ne cite AUCUN concurrent nommé.
4. N'invente AUCUN service hors catalogue (Arduino, IA Initiation, IA Professionnel, IA Dev).
5. Ne prends AUCUN engagement ferme sur une date de début ou calendrier (CHRONOS non disponible).
6. Prix à mentionner (si pertinent) : {calculated_price if calculated_price else 'ne pas mentionner de prix si non requis'} FCFA.
7. Signature obligatoire : Akim — ZENITH AI.
"""

        prompt = f"""Rédige la réponse à cet email entrant :
Expéditeur : {contact.get('nom')} ({contact.get('email')})
Sujet : {incoming_subject}
Message :
{incoming_content}
"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            text = response.text.strip()
            # Nettoyer les balises éventuelles
            text = re.sub(r"^```markdown\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return text
        except Exception:
            return self.draft_fallback(contact, incoming_content, service_id, calculated_price, is_tutoiement)
