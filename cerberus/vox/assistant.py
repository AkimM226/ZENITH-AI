"""
CERBERUS VOX - Assistant Conversationnel avec Garde-fous Stricts
Section 3.4 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md
"""
import re
from typing import Optional, Dict, Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from cerberus.config import GEMINI_API_KEY, GEMINI_MODEL
from cerberus.vox.tools import VoxDataTools


class VoxAssistant:
    """
    Cerveau conversationnel de VOX.
    Connecté à Gemini pour la compréhension sémantique, avec repli déterministe.
    Applique le protocole inviolable de confirmation verbale avant toute action.
    """

    def __init__(self, data_tools: Optional[VoxDataTools] = None, api_key: Optional[str] = None):
        self.tools = data_tools or VoxDataTools()
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

        # Gestion de l'état de confirmation préalable
        self.pending_confirmation: Optional[Dict[str, Any]] = None

    def _interpret_intent_rule_based(self, query: str) -> Dict[str, Any]:
        """Interprétation déterministe robuste des demandes orales fréquentes."""
        q = query.lower().strip()

        # Demande de confirmation en cours
        if self.pending_confirmation:
            if re.search(r"\b(oui|confirme|valide|d['’]accord|exactement|vas-y|fais-le|go)\b", q):
                return {"intent": "CONFIRM_ACTION", "action": self.pending_confirmation}
            elif re.search(r"\b(non|annule|stop|pas maintenant|laisse|refuse)\b", q):
                return {"intent": "CANCEL_ACTION", "action": self.pending_confirmation}

        # Action spécifique : Valider un brouillon (prioritaire sur la simple consultation)
        val_match = re.search(r"\b(valide|approuve|confirme)\s+(le\s+)?brouillon\s*(numéro|n°|#)?\s*(\d+)", q)
        if val_match:
            draft_id = int(val_match.group(4))
            return {"intent": "REQUEST_VALIDATE_DRAFT", "draft_id": draft_id}

        # Action spécifique : Résoudre une alerte (prioritaire sur la simple consultation)
        res_match = re.search(r"\b(résous|classe|ferme)\s+(l['’]\s*)?alerte\s*(numéro|n°|#)?\s*(\d+)", q)
        if res_match:
            alert_id = int(res_match.group(4))
            return {"intent": "REQUEST_RESOLVE_ALERT", "alert_id": alert_id}

        # Demande de briefing
        if re.search(r"\b(briefing|situation|point|résumé|quoi de neuf|nouvelles?|rapport)\b", q):
            return {"intent": "GET_BRIEFING"}

        # Consultation des alertes
        if re.search(r"\b(alertes?|urgences?|problèmes?|critiques?|dangereux)\b", q):
            return {"intent": "GET_ALERTS"}

        # Consultation des brouillons
        if re.search(r"\b(brouillons?|messages? en attente|emails? à valider|réponses? en attente)\b", q):
            return {"intent": "GET_DRAFTS"}

        # Salutations
        if re.search(r"\b(bonjour|salut|hello|coucou|bonsoir)\b", q):
            return {"intent": "GREETING"}

        return {"intent": "UNKNOWN"}

    def respond(self, user_query: str) -> str:
        """Traite la demande vocale et retourne la réponse orale appropriée."""
        intent_info = self._interpret_intent_rule_based(user_query)
        intent = intent_info["intent"]

        # Traitement de la confirmation d'action
        if intent == "CONFIRM_ACTION":
            action = intent_info["action"]
            self.pending_confirmation = None
            if action["type"] == "validate_draft":
                res = self.tools.execute_draft_validation(action["id"])
                return res["message"]
            elif action["type"] == "resolve_alert":
                res = self.tools.execute_alert_resolution(action["id"])
                return res["message"]

        if intent == "CANCEL_ACTION":
            self.pending_confirmation = None
            return "Action annulée. Aucune modification n'a été effectuée."

        # Demande de briefing
        if intent == "GET_BRIEFING":
            return self.tools.get_oral_briefing()

        # Demande des alertes
        if intent == "GET_ALERTS":
            return self.tools.get_alerts_summary()

        # Demande des brouillons
        if intent == "GET_DRAFTS":
            return self.tools.get_drafts_summary()

        # Demande de validation avec déclenchement du protocole de confirmation
        if intent == "REQUEST_VALIDATE_DRAFT":
            draft_id = intent_info["draft_id"]
            self.pending_confirmation = {"type": "validate_draft", "id": draft_id}
            return f"Akim, confirmez-vous explicitement la validation du brouillon numéro {draft_id} pour envoi ? Dites oui pour confirmer ou non pour annuler."

        # Demande de résolution d'alerte avec confirmation
        if intent == "REQUEST_RESOLVE_ALERT":
            alert_id = intent_info["alert_id"]
            self.pending_confirmation = {"type": "resolve_alert", "id": alert_id}
            return f"Confirmez-vous le classement de l'alerte numéro {alert_id} ? Dites oui ou confirmez."

        if intent == "GREETING":
            return "Bonjour Akim. Je suis VOX, votre assistant CERBERUS. Que souhaitez-vous consulter ?"

        # Si l'intention déterministe est inconnue et que Gemini est disponible, on sollicite l'IA
        if self.client:
            try:
                briefing_context = self.tools.get_oral_briefing()
                prompt = f"""Tu es VOX, l'assistant vocal personnel d'Akim pour le système CERBERUS (ZENITH AI).
Règles strictes :
- Réponds de manière concise, directe et adaptée à la voix (1 à 3 phrases claires).
- Ne propose JAMAIS d'actions sur des clients réels.
- Si Akim demande des infos sur l'activité, utilise ce contexte actuel : {briefing_context}

Demande d'Akim : {user_query}
Réponse vocale :"""
                res = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )
                return res.text.strip()
            except Exception:
                pass

        return "Je n'ai pas bien compris votre demande. Vous pouvez me demander le briefing, les alertes en cours, ou les brouillons en attente."
