"""
CERBERUS VOX - Assistant Conversationnel avec Mémoire Court Terme & Garde-fous
Sections 3, 5 et 7 du document ADDENDUM_2_ORBE_INTERFACE.md
"""
import re
import time
from typing import Optional, Dict, Any, List

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from cerberus.config import GEMINI_API_KEY, GEMINI_MODEL
from cerberus.vox.tools import VoxDataTools


class VoxAssistant:
    """
    Cerveau conversationnel de l'Orbe et de VOX.
    Maintient un historique court terme et résout les références anaphoriques
    ('la première alerte', 'ce brouillon', etc.).
    Protocole strict de confirmation verbale avant toute action.
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

        # État de confirmation préalable
        self.pending_confirmation: Optional[Dict[str, Any]] = None

        # Mémoire court terme (Section 5 Addendum 2)
        self.conversation_history: List[Dict[str, str]] = []
        self.last_mentioned_alerts: List[Dict[str, Any]] = []
        self.last_mentioned_drafts: List[Dict[str, Any]] = []
        self.last_activity_time: float = time.time()

    def _clean_old_history_if_inactive(self, max_idle_seconds: int = 600):
        """Réinitialise la mémoire après 10 minutes d'inactivité."""
        now = time.time()
        if now - self.last_activity_time > max_idle_seconds:
            self.conversation_history.clear()
            self.last_mentioned_alerts.clear()
            self.last_mentioned_drafts.clear()
            self.pending_confirmation = None
        self.last_activity_time = now

    def _resolve_relative_index(self, text: str) -> Optional[int]:
        """Convertit 'premier/première', 'deuxième', 'troisième', '1er', etc. en index 0-based."""
        t = text.lower()
        if re.search(r"\b(premi[eè]re?|1er|1[eè]re|ce|cette|celui-l[àa])\b", t):
            return 0
        if re.search(r"\b(deuxi[eè]me|2[eè]me|second|seconde)\b", t):
            return 1
        if re.search(r"\b(troisi[eè]me|3[eè]me)\b", t):
            return 2
        return None

    def _interpret_intent_rule_based(self, query: str) -> Dict[str, Any]:
        """Interprétation déterministe avec résolution contextuelle des références."""
        self._clean_old_history_if_inactive()
        q = query.lower().strip()

        # 1. Demande de confirmation en cours
        if self.pending_confirmation:
            if re.search(r"\b(oui|confirme|valide|d['’]accord|exactement|vas-y|fais-le|go)\b", q):
                return {"intent": "CONFIRM_ACTION", "action": self.pending_confirmation}
            elif re.search(r"\b(non|annule|stop|pas maintenant|laisse|refuse)\b", q):
                return {"intent": "CANCEL_ACTION", "action": self.pending_confirmation}

        # 2. Commandes de contrôle de l'Orbe / Fenêtre Desktop (Addendum 2 Section 2.2)
        if re.search(r"\b(passe en mode omnipr[ée]sent|r[ée]duis-toi|mode discret|mode flottant|flotte)\b", q):
            return {"intent": "UI_MINIMIZE"}
        if re.search(r"\b(plein [ée]cran|fen[êe]tre compl[èe]te|reviens en plein|agrandis|ouvre grand)\b", q):
            return {"intent": "UI_RESTORE"}
        if re.search(r"\b(tableau de bord|mode classique|vue compl[èe]te|laisse-moi valider moi-m[êe]me|mode manuel)\b", q):
            return {"intent": "UI_OPEN_MANUAL"}
        if re.search(r"\b(merci|c['’]est bon|ferme|fermer|efface|effacer|tr[èe]s bien|parfait)\b", q):
            return {"intent": "UI_DISMISS_CARD"}

        # 3. Actions avec ID explicite : Valider un brouillon
        val_match = re.search(r"\b(valide|approuve|confirme)\s+(le\s+)?brouillon\s*(num[ée]ro|n°|#)?\s*(\d+)", q)
        if val_match:
            draft_id = int(val_match.group(4))
            return {"intent": "REQUEST_VALIDATE_DRAFT", "draft_id": draft_id}

        # 4. Actions avec ID explicite : Résoudre une alerte
        res_match = re.search(r"\b(r[ée]sous|classe|ferme)\s+(l['’]\s*)?alerte\s*(num[ée]ro|n°|#)?\s*(\d+)", q)
        if res_match:
            alert_id = int(res_match.group(4))
            return {"intent": "REQUEST_RESOLVE_ALERT", "alert_id": alert_id}

        # 5. RÉSOLUTION CONTEXTUELLE DE RÉFÉRENCE (Section 5 Addendum 2)
        # Ex : "résous la première", "classe celle-ci", "traite la deuxième"
        if re.search(r"\b(r[ée]sous|classe|traite)\b", q):
            idx = self._resolve_relative_index(q)
            if idx is not None and self.last_mentioned_alerts and idx < len(self.last_mentioned_alerts):
                target_alert = self.last_mentioned_alerts[idx]
                return {
                    "intent": "REQUEST_RESOLVE_ALERT",
                    "alert_id": target_alert["id"],
                    "context_ref": f"Alerte #{target_alert['id']} ({target_alert.get('motif', '')})"
                }

        # Ex : "valide le premier", "valide celui-ci", "approuve la première"
        if re.search(r"\b(valide|approuve|envoie)\b", q):
            idx = self._resolve_relative_index(q)
            if idx is not None and self.last_mentioned_drafts and idx < len(self.last_mentioned_drafts):
                target_draft = self.last_mentioned_drafts[idx]
                return {
                    "intent": "REQUEST_VALIDATE_DRAFT",
                    "draft_id": target_draft["id"],
                    "context_ref": f"Brouillon #{target_draft['id']} pour {target_draft.get('email_destinataire', '')}"
                }

        # 6. Demande de briefing
        if re.search(r"\b(briefing|situation|point|r[ée]sum[ée]|quoi de neuf|nouvelles?|rapport)\b", q):
            return {"intent": "GET_BRIEFING"}

        # 7. Consultation des alertes
        if re.search(r"\b(alertes?|urgences?|probl[èe]mes?|critiques?|dangereux)\b", q):
            return {"intent": "GET_ALERTS"}

        # 8. Consultation des brouillons
        if re.search(r"\b(brouillons?|messages? en attente|emails? [àa] valider|r[ée]ponses? en attente)\b", q):
            return {"intent": "GET_DRAFTS"}

        # 9. Salutations
        if re.search(r"\b(bonjour|salut|hello|coucou|bonsoir)\b", q):
            return {"intent": "GREETING"}

        return {"intent": "UNKNOWN"}

    def interact(self, user_query: str) -> Dict[str, Any]:
        """
        Traite la requête et retourne une réponse enrichie pour l'Orbe (texte, cartes, actions UI).
        """
        intent_info = self._interpret_intent_rule_based(user_query)
        intent = intent_info["intent"]

        response_text = ""
        context_card = None
        ui_action = None

        # Actions d'interface (UI)
        if intent == "UI_MINIMIZE":
            response_text = "Je passe en mode omniprésent discret."
            ui_action = "minimize"
            context_card = None
        elif intent == "UI_RESTORE":
            response_text = "Je rétablis la fenêtre complète."
            ui_action = "restore"
        elif intent == "UI_OPEN_MANUAL":
            response_text = "Voici le tableau de bord classique avec tous les détails."
            ui_action = "open_manual"
        elif intent == "UI_DISMISS_CARD":
            response_text = "C'est noté, Akim. Je referme les informations."
            ui_action = "dismiss_card"
            self.last_mentioned_alerts.clear()
            self.last_mentioned_drafts.clear()

        # Confirmation / Annulation
        elif intent == "CONFIRM_ACTION":
            action = intent_info["action"]
            self.pending_confirmation = None
            if action["type"] == "validate_draft":
                res = self.tools.execute_draft_validation(action["id"])
                response_text = res["message"]
            elif action["type"] == "resolve_alert":
                res = self.tools.execute_alert_resolution(action["id"])
                response_text = res["message"]
            ui_action = "refresh_data"

        elif intent == "CANCEL_ACTION":
            self.pending_confirmation = None
            response_text = "Action annulée. Aucune modification n'a été effectuée."

        # Demande de Briefing
        elif intent == "GET_BRIEFING":
            oral, data = self.tools.get_briefing_full_data()
            response_text = oral
            self.last_mentioned_alerts = (data.get("urgent_alerts", []) + data.get("standard_alerts", []))[:3]
            self.last_mentioned_drafts = data.get("pending_drafts", [])[:3]
            context_card = {
                "type": "briefing",
                "title": "Point de Situation CERBERUS",
                "metrics": data.get("metrics", {}),
                "urgent_alerts_count": len(data.get("urgent_alerts", [])),
                "pending_drafts_count": len(data.get("pending_drafts", []))
            }

        # Demande des Alertes
        elif intent == "GET_ALERTS":
            oral, alerts = self.tools.get_alerts_data()
            response_text = oral
            self.last_mentioned_alerts = alerts[:3]
            if alerts:
                context_card = {
                    "type": "alerts",
                    "title": f"Alertes Actives ({len(alerts)})",
                    "items": [
                        {
                            "id": a["id"],
                            "niveau": a.get("niveau", "STANDARD"),
                            "motif": a.get("motif", ""),
                            "contact": a.get("contact_nom") or a.get("contact_email") or "Inconnu"
                        }
                        for a in alerts[:5]
                    ]
                }

        # Demande des Brouillons
        elif intent == "GET_DRAFTS":
            oral, drafts = self.tools.get_drafts_data()
            response_text = oral
            self.last_mentioned_drafts = drafts[:3]
            if drafts:
                context_card = {
                    "type": "drafts",
                    "title": f"Brouillons à Valider ({len(drafts)})",
                    "items": [
                        {
                            "id": d["id"],
                            "sujet": d.get("email_sujet", "Sans objet"),
                            "destinataire": d.get("email_destinataire", ""),
                            "motif": d.get("motif_blocage", ""),
                            "corps": d.get("corps_propose", "")[:120] + "..."
                        }
                        for d in drafts[:5]
                    ]
                }

        # Demande de validation avec déclenchement du protocole de confirmation
        elif intent == "REQUEST_VALIDATE_DRAFT":
            draft_id = intent_info["draft_id"]
            self.pending_confirmation = {"type": "validate_draft", "id": draft_id}
            response_text = f"Akim, confirmez-vous explicitement la validation du brouillon numéro {draft_id} pour envoi ? Dites oui pour confirmer ou non pour annuler."

        # Demande de résolution d'alerte avec confirmation
        elif intent == "REQUEST_RESOLVE_ALERT":
            alert_id = intent_info["alert_id"]
            self.pending_confirmation = {"type": "resolve_alert", "id": alert_id}
            response_text = f"Confirmez-vous le classement de l'alerte numéro {alert_id} ? Dites oui ou confirmez."

        elif intent == "GREETING":
            response_text = "Bonjour Akim. Je suis l'Orbe CERBERUS, à votre écoute. Que souhaitez-vous consulter ?"

        # Fallback Gemini avec historique conversationnel
        else:
            if self.client:
                try:
                    briefing_context = self.tools.get_oral_briefing()
                    history_str = "\n".join([f"{h['role']}: {h['text']}" for h in self.conversation_history[-4:]])
                    prompt = f"""Tu es l'Orbe de présence et l'assistant vocal personnel d'Akim pour CERBERUS (ZENITH AI).
Règles strictes :
- Réponds de manière concise, directe et adaptée à la voix (1 à 3 phrases claires).
- Ne propose JAMAIS d'actions engageantes sur des clients réels.
- Contexte CERBERUS actuel : {briefing_context}
- Historique récent :
{history_str}

Demande d'Akim : {user_query}
Réponse :"""
                    res = self.client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt
                    )
                    response_text = res.text.strip()
                except Exception:
                    response_text = "Je n'ai pas bien saisi votre demande. Vous pouvez me demander le briefing, les alertes, ou les brouillons en attente."
            else:
                response_text = "Je n'ai pas bien compris votre demande. Vous pouvez me demander le briefing, les alertes, ou les brouillons en attente."

        # Enregistrement dans l'historique
        self.conversation_history.append({"role": "Akim", "text": user_query})
        self.conversation_history.append({"role": "Orbe", "text": response_text})
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]

        return {
            "text": response_text,
            "intent": intent,
            "context_card": context_card,
            "ui_action": ui_action,
            "requires_confirmation": bool(self.pending_confirmation)
        }

    def respond(self, user_query: str) -> str:
        """Méthode de compatibilité retournant directement le texte de réponse."""
        res = self.interact(user_query)
        return res["text"]
