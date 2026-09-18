"""
CERBERUS VOX - Assistant Conversationnel avec Function Calling Gemini Natif
Addendum 4 : Gemini devient le cerveau decisonnel principal.
Les garde-fous de confirmation restent geres exclusivement cote Python.
"""
import re
import time
from typing import Optional, Dict, Any, List

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from cerberus.config import GEMINI_API_KEY, GEMINI_MODEL
from cerberus.vox.tools import VoxDataTools


# ---------------------------------------------------------------------------
# Declarations des outils pour le function calling Gemini
# Note : execute_draft_validation et execute_alert_resolution ne sont
# JAMAIS exposes a Gemini - seule la confirmation Python debloque ces actions.
# ---------------------------------------------------------------------------

_TOOL_DECLARATIONS = [
    {
        "name": "get_briefing",
        "description": (
            "Obtenir la synthese complete de la situation commerciale actuelle de CERBERUS : "
            "nombre d alertes, de brouillons en attente, de prospects, et les points d attention prioritaires."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_alerts",
        "description": (
            "Lister les alertes commerciales en attente de traitement, classees par urgence. "
            "Appeler quand Akim demande les alertes, les problemes, ou les urgences."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_drafts",
        "description": (
            "Lister les brouillons d emails en attente de validation par Akim. "
            "Appeler quand il demande les brouillons, messages en attente, ou emails a valider."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "request_validate_draft",
        "description": (
            "Demarrer le protocole de confirmation pour valider et envoyer un brouillon d email. "
            "Cette fonction NE VALIDE PAS immediatement - elle demande une confirmation explicite a Akim. "
            "Appeler quand Akim veut valider, approuver, ou envoyer un brouillon precis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "integer", "description": "L identifiant numerique du brouillon a valider."}
            },
            "required": ["draft_id"]
        }
    },
    {
        "name": "request_resolve_alert",
        "description": (
            "Demarrer le protocole de confirmation pour resoudre et classer une alerte. "
            "Cette fonction NE RESOUT PAS immediatement - elle demande une confirmation explicite a Akim. "
            "Appeler quand Akim veut resoudre, classer, ou fermer une alerte precise."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "alert_id": {"type": "integer", "description": "L identifiant numerique de l alerte a resoudre."}
            },
            "required": ["alert_id"]
        }
    },
    {
        "name": "switch_to_omnipresent_mode",
        "description": (
            "Passer l interface Orbe en mode flottant omnipresent : fenetre compacte, always-on-top. "
            "Appeler quand Akim veut reduire l interface, passer en mode discret, ou flotter."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "switch_to_fullscreen_mode",
        "description": (
            "Revenir en fenetre complete depuis le mode omnipresent. "
            "Appeler quand Akim demande le plein ecran, agrandir, ou revenir a la fenetre normale."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "open_manual_dashboard",
        "description": (
            "Ouvrir le tableau de bord classique CERBERUS avec vue complete des donnees. "
            "Appeler quand Akim veut valider manuellement, voir le mode classique, ou acceder au dashboard."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
]


def _build_gemini_tools():
    """Construit la liste d outils au format google-genai si disponible."""
    if types is None:
        return None
    try:
        declarations = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"]
            )
            for t in _TOOL_DECLARATIONS
        ]
        return [types.Tool(function_declarations=declarations)]
    except Exception:
        return None


class VoxAssistant:
    """
    Cerveau conversationnel de l Orbe et de VOX.
    Architecture Addendum 4 : Gemini function calling comme decideur principal.
    Memoire court terme et garde-fous de confirmation strictement conserves.
    """

    def __init__(self, data_tools: Optional[VoxDataTools] = None, api_key: Optional[str] = None):
        self.tools = data_tools or VoxDataTools()
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        self._gemini_tools = _build_gemini_tools()

        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

        # Etat de confirmation prealable (garde-fou inviolable)
        self.pending_confirmation: Optional[Dict[str, Any]] = None

        # Memoire court terme
        self.conversation_history: List[Dict[str, str]] = []
        self.last_mentioned_alerts: List[Dict[str, Any]] = []
        self.last_mentioned_drafts: List[Dict[str, Any]] = []
        self.last_activity_time: float = time.time()

    def _clean_old_history_if_inactive(self, max_idle_seconds: int = 600):
        """Reinitialise la memoire apres 10 minutes d inactivite."""
        now = time.time()
        if now - self.last_activity_time > max_idle_seconds:
            self.conversation_history.clear()
            self.last_mentioned_alerts.clear()
            self.last_mentioned_drafts.clear()
            self.pending_confirmation = None
        self.last_activity_time = now

    def _resolve_relative_index(self, text: str) -> Optional[int]:
        """Fallback regex : convertit premier/premiere, 2eme, etc. en index 0-based."""
        t = text.lower()
        if re.search(r"\b(premi[ee]re?|1er|1[ee]re|ce|cette|celui-l[aa])\b", t):
            return 0
        if re.search(r"\b(deuxi[ee]me|2[ee]me|second|seconde)\b", t):
            return 1
        if re.search(r"\b(troisi[ee]me|3[ee]me)\b", t):
            return 2
        return None

    def _build_system_context(self) -> str:
        """Construit le prompt systeme injecte dans chaque appel Gemini."""
        briefing = self.tools.get_oral_briefing()

        context_refs = ""
        if self.last_mentioned_alerts:
            alert_refs = ", ".join(
                f"Alerte #{a['id']} ({a.get('motif', '?')})"
                for a in self.last_mentioned_alerts
            )
            context_refs += f"\nAlertes mentionnees recemment : {alert_refs}"
        if self.last_mentioned_drafts:
            draft_refs = ", ".join(
                f"Brouillon #{d['id']} ({d.get('email_destinataire', '?')})"
                for d in self.last_mentioned_drafts
            )
            context_refs += f"\nBrouillons mentionnes recemment : {draft_refs}"

        history_str = ""
        if self.conversation_history:
            history_str = "\n".join(
                f"{h['role']}: {h['text']}" for h in self.conversation_history[-6:]
            )

        return (
            "Tu es l Orbe CERBERUS, l assistant vocal personnel d Akim (ZENITH AI, Bobo-Dioulasso).\n\n"
            "REGLES ABSOLUES :\n"
            "- Reponds de maniere concise, directe et adaptee a la voix (1 a 3 phrases maximum).\n"
            "- Ne propose JAMAIS d actions engageantes sans passer par une fonction de confirmation.\n"
            "- Si Akim fait reference a 'la premiere alerte', 'le deuxieme brouillon', etc., utilise "
            "les listes de contexte ci-dessous pour identifier l ID correct.\n"
            "- Ne fabrique jamais d ID ou de donnees.\n\n"
            f"SITUATION CERBERUS ACTUELLE :\n{briefing}\n{context_refs}\n\n"
            f"HISTORIQUE RECENT :\n{history_str if history_str else '(Debut de conversation)'}"
        )

    def _handle_confirmation_input(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Si une confirmation est en attente, verifie si la reponse est oui/non.
        Retourne un resultat structure ou None si aucune confirmation en attente.
        """
        if not self.pending_confirmation:
            return None

        q = query.lower().strip()
        if re.search(r"\b(oui|confirme|valide|d[''']accord|exactement|vas-y|fais-le|go)\b", q):
            action = self.pending_confirmation
            self.pending_confirmation = None
            if action["type"] == "validate_draft":
                res = self.tools.execute_draft_validation(action["id"])
                return {
                    "text": res["message"], "intent": "CONFIRM_ACTION",
                    "context_card": None, "ui_action": "refresh_data", "requires_confirmation": False
                }
            elif action["type"] == "resolve_alert":
                res = self.tools.execute_alert_resolution(action["id"])
                return {
                    "text": res["message"], "intent": "CONFIRM_ACTION",
                    "context_card": None, "ui_action": "refresh_data", "requires_confirmation": False
                }

        if re.search(r"\b(non|annule|stop|pas maintenant|laisse|refuse)\b", q):
            self.pending_confirmation = None
            return {
                "text": "Action annulee. Aucune modification n a ete effectuee.",
                "intent": "CANCEL_ACTION", "context_card": None, "ui_action": None, "requires_confirmation": False
            }

        return None  # Reponse ambigue — Gemini gere la suite

    def _dispatch_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute l outil demande par Gemini et retourne la reponse structuree."""
        if tool_name == "get_briefing":
            oral, data = self.tools.get_briefing_full_data()
            self.last_mentioned_alerts = (data.get("urgent_alerts", []) + data.get("standard_alerts", []))[:3]
            self.last_mentioned_drafts = data.get("pending_drafts", [])[:3]
            card = {
                "type": "briefing", "title": "Point de Situation CERBERUS",
                "metrics": data.get("metrics", {}),
                "urgent_alerts_count": len(data.get("urgent_alerts", [])),
                "pending_drafts_count": len(data.get("pending_drafts", []))
            }
            return {"text": oral, "context_card": card, "ui_action": None, "intent": "GET_BRIEFING"}

        elif tool_name == "get_alerts":
            oral, alerts = self.tools.get_alerts_data()
            self.last_mentioned_alerts = alerts[:3]
            card = None
            if alerts:
                card = {
                    "type": "alerts", "title": f"Alertes Actives ({len(alerts)})",
                    "items": [
                        {"id": a["id"], "niveau": a.get("niveau", "STANDARD"),
                         "motif": a.get("motif", ""),
                         "contact": a.get("contact_nom") or a.get("contact_email") or "Inconnu"}
                        for a in alerts[:5]
                    ]
                }
            return {"text": oral, "context_card": card, "ui_action": None, "intent": "GET_ALERTS"}

        elif tool_name == "get_drafts":
            oral, drafts = self.tools.get_drafts_data()
            self.last_mentioned_drafts = drafts[:3]
            card = None
            if drafts:
                card = {
                    "type": "drafts", "title": f"Brouillons a Valider ({len(drafts)})",
                    "items": [
                        {"id": d["id"], "sujet": d.get("email_sujet", "Sans objet"),
                         "destinataire": d.get("email_destinataire", ""),
                         "motif": d.get("motif_blocage", ""),
                         "corps": d.get("corps_propose", "")[:120] + "..."}
                        for d in drafts[:5]
                    ]
                }
            return {"text": oral, "context_card": card, "ui_action": None, "intent": "GET_DRAFTS"}

        elif tool_name == "request_validate_draft":
            draft_id = int(tool_args.get("draft_id", 0))
            self.pending_confirmation = {"type": "validate_draft", "id": draft_id}
            text = (
                f"Akim, confirmez-vous explicitement la validation du brouillon numero {draft_id} "
                f"pour envoi ? Dites oui pour confirmer ou non pour annuler."
            )
            return {"text": text, "context_card": None, "ui_action": None, "intent": "REQUEST_VALIDATE_DRAFT"}

        elif tool_name == "request_resolve_alert":
            alert_id = int(tool_args.get("alert_id", 0))
            self.pending_confirmation = {"type": "resolve_alert", "id": alert_id}
            text = f"Confirmez-vous le classement de l alerte numero {alert_id} ? Dites oui ou confirmez."
            return {"text": text, "context_card": None, "ui_action": None, "intent": "REQUEST_RESOLVE_ALERT"}

        elif tool_name == "switch_to_omnipresent_mode":
            return {"text": "Je passe en mode omnipresent discret.", "context_card": None, "ui_action": "minimize", "intent": "UI_MINIMIZE"}

        elif tool_name == "switch_to_fullscreen_mode":
            return {"text": "Je retablis la fenetre complete.", "context_card": None, "ui_action": "restore", "intent": "UI_RESTORE"}

        elif tool_name == "open_manual_dashboard":
            return {"text": "Voici le tableau de bord classique avec tous les details.", "context_card": None, "ui_action": "open_manual", "intent": "UI_OPEN_MANUAL"}

        return {"text": "Je ne reconnais pas cet outil.", "context_card": None, "ui_action": None, "intent": "UNKNOWN"}

    def _call_gemini_with_tools(self, user_query: str) -> Dict[str, Any]:
        """
        Coeur de l architecture Addendum 4 :
        1. Envoie la requete + contexte + outils a Gemini
        2. Si Gemini appelle un outil -> on l execute -> on renvoie le resultat a Gemini
        3. Gemini formule la reponse finale en langage naturel
        """
        if not self.client or not self._gemini_tools:
            return self._fallback_response(user_query)

        system_instruction = self._build_system_context()

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_query,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=self._gemini_tools,
                    temperature=0.2,
                )
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate:
                return self._fallback_response(user_query)

            part = candidate.content.parts[0] if candidate.content.parts else None
            if not part:
                return self._fallback_response(user_query)

            # Gemini a choisi d appeler un outil
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                tool_result = self._dispatch_tool_call(tool_name, tool_args)

                # Tour 2 : renvoyer le resultat a Gemini pour la reponse finale
                tool_response_part = types.Part.from_function_response(
                    name=tool_name,
                    response={"result": tool_result["text"]}
                )
                final_response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[
                        types.Content(role="user", parts=[types.Part.from_text(user_query)]),
                        types.Content(role="model", parts=[part]),
                        types.Content(role="user", parts=[tool_response_part]),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3,
                    )
                )
                final_text = final_response.text.strip() if final_response.text else tool_result["text"]

                return {
                    "text": final_text,
                    "intent": tool_result.get("intent", "TOOL_CALL"),
                    "context_card": tool_result.get("context_card"),
                    "ui_action": tool_result.get("ui_action"),
                    "requires_confirmation": bool(self.pending_confirmation)
                }

            # Gemini a repondu directement (conversation generale)
            direct_text = response.text.strip() if response.text else ""
            if not direct_text:
                return self._fallback_response(user_query)

            return {
                "text": direct_text, "intent": "CONVERSATION",
                "context_card": None, "ui_action": None,
                "requires_confirmation": bool(self.pending_confirmation)
            }

        except Exception as e:
            print(f"[!] Erreur Gemini function calling : {e}")
            return self._fallback_response(user_query)

    def _fallback_response(self, user_query: str) -> Dict[str, Any]:
        """Degradation gracieuse si Gemini est indisponible (offline, pas de cle API, quota).

        Ordre des verifications (important) :
        1. Actions avec ID explicite (valider brouillon N, resoudre alerte N) EN PREMIER
        2. Resolution contextuelle (la premiere, etc.)
        3. Commandes de liste generales (brouillons, alertes, briefing)
        4. UI actions
        5. Salutations
        """
        q = user_query.lower().strip()

        # 1a. Valider brouillon avec ID explicite (AVANT le pattern generique brouillons?)
        val_match = re.search(
            r"\b(valide|approuve|confirme)\s+(le\s+)?brouillon\s*(?:num[ee]ro|n[o]?|#)?\s*(\d+)", q
        )
        if val_match:
            draft_id = int(val_match.group(3))
            self.pending_confirmation = {"type": "validate_draft", "id": draft_id}
            return {
                "text": f"Akim, confirmez-vous explicitement la validation du brouillon numero {draft_id} pour envoi ? Dites oui pour confirmer ou non pour annuler.",
                "intent": "REQUEST_VALIDATE_DRAFT", "context_card": None, "ui_action": None, "requires_confirmation": True
            }

        # 1b. Resoudre alerte avec ID explicite (AVANT le pattern generique alertes?)
        res_match = re.search(
            r"\b(r[\xe9e]sous|classe|ferme)\s+(l[\'\u2019]\s*)?alerte\s*(?:num[ee]ro|n[o]?|#)?\s*(\d+)", q
        )
        if res_match:
            alert_id = int(res_match.group(3))
            self.pending_confirmation = {"type": "resolve_alert", "id": alert_id}
            return {
                "text": f"Confirmez-vous le classement de l alerte numero {alert_id} ? Dites oui ou confirmez.",
                "intent": "REQUEST_RESOLVE_ALERT", "context_card": None, "ui_action": None, "requires_confirmation": True
            }

        # 2. Resolution contextuelle de reference
        if re.search(r"\b(r[\xe9e]sous|classe|traite)\b", q):
            idx = self._resolve_relative_index(q)
            if idx is not None and self.last_mentioned_alerts and idx < len(self.last_mentioned_alerts):
                alert_id = self.last_mentioned_alerts[idx]["id"]
                self.pending_confirmation = {"type": "resolve_alert", "id": alert_id}
                return {
                    "text": f"Confirmez-vous le classement de l alerte numero {alert_id} ? Dites oui ou confirmez.",
                    "intent": "REQUEST_RESOLVE_ALERT", "context_card": None, "ui_action": None, "requires_confirmation": True
                }
        if re.search(r"\b(valide|approuve|envoie)\b", q):
            idx = self._resolve_relative_index(q)
            if idx is not None and self.last_mentioned_drafts and idx < len(self.last_mentioned_drafts):
                draft_id = self.last_mentioned_drafts[idx]["id"]
                self.pending_confirmation = {"type": "validate_draft", "id": draft_id}
                return {
                    "text": f"Akim, confirmez-vous explicitement la validation du brouillon numero {draft_id} pour envoi ? Dites oui pour confirmer ou non pour annuler.",
                    "intent": "REQUEST_VALIDATE_DRAFT", "context_card": None, "ui_action": None, "requires_confirmation": True
                }

        # 3. Commandes de liste generales (apres les actions specifiques)
        if re.search(r"\b(briefing|situation|point|r[\xe9e]sum[\xe9e]|quoi de neuf|nouvelles?|rapport)\b", q):
            oral, data = self.tools.get_briefing_full_data()
            self.last_mentioned_alerts = (data.get("urgent_alerts", []) + data.get("standard_alerts", []))[:3]
            self.last_mentioned_drafts = data.get("pending_drafts", [])[:3]
            return {
                "text": oral, "intent": "GET_BRIEFING",
                "context_card": {"type": "briefing", "title": "Point de Situation", "metrics": data.get("metrics", {}),
                                  "urgent_alerts_count": len(data.get("urgent_alerts", [])),
                                  "pending_drafts_count": len(data.get("pending_drafts", []))},
                "ui_action": None, "requires_confirmation": False
            }
        if re.search(r"\b(alertes?|urgences?|probl[\xe8e]mes?)\b", q):
            oral, alerts = self.tools.get_alerts_data()
            self.last_mentioned_alerts = alerts[:3]
            card = {"type": "alerts", "title": f"Alertes ({len(alerts)})",
                    "items": [{"id": a["id"], "niveau": a.get("niveau", "STANDARD"),
                                "motif": a.get("motif", ""), "contact": a.get("contact_email", "")}
                               for a in alerts[:5]]} if alerts else None
            return {"text": oral, "intent": "GET_ALERTS", "context_card": card, "ui_action": None, "requires_confirmation": False}
        if re.search(r"\b(brouillons?|messages? en attente|emails? [a\xe0] valider)\b", q):
            oral, drafts = self.tools.get_drafts_data()
            self.last_mentioned_drafts = drafts[:3]
            card = {"type": "drafts", "title": f"Brouillons ({len(drafts)})",
                    "items": [{"id": d["id"], "sujet": d.get("email_sujet", ""),
                                "destinataire": d.get("email_destinataire", ""),
                                "motif": d.get("motif_blocage", ""), "corps": d.get("corps_propose", "")[:120] + "..."}
                               for d in drafts[:5]]} if drafts else None
            return {"text": oral, "intent": "GET_DRAFTS", "context_card": card, "ui_action": None, "requires_confirmation": False}

        # 4. Actions UI
        if re.search(r"\b(omnipr[\xe9e]sent|mode discret|flottant|flotte|r[\xe9e]duis)\b", q):
            return {"text": "Je passe en mode omnipresent discret.", "intent": "UI_MINIMIZE",
                    "context_card": None, "ui_action": "minimize", "requires_confirmation": False}
        if re.search(r"\b(plein [\xe9e]cran|fen[\xeae]tre compl[\xe8e]te|agrandis)\b", q):
            return {"text": "Je retablis la fenetre complete.", "intent": "UI_RESTORE",
                    "context_card": None, "ui_action": "restore", "requires_confirmation": False}
        if re.search(r"\b(tableau de bord|mode classique|mode manuel)\b", q):
            return {"text": "Voici le tableau de bord classique.", "intent": "UI_OPEN_MANUAL",
                    "context_card": None, "ui_action": "open_manual", "requires_confirmation": False}
        if re.search(r"\b(merci|c[\'\u2019]est bon|ferme|efface)\b", q):
            self.last_mentioned_alerts.clear()
            self.last_mentioned_drafts.clear()
            return {"text": "C est note, Akim.", "intent": "UI_DISMISS_CARD",
                    "context_card": None, "ui_action": "dismiss_card", "requires_confirmation": False}

        # 5. Salutations
        if re.search(r"\b(bonjour|salut|hello|coucou|bonsoir)\b", q):
            return {
                "text": "Bonjour Akim. Je suis l Orbe CERBERUS, a votre ecoute. Que souhaitez-vous consulter ?",
                "intent": "GREETING", "context_card": None, "ui_action": None, "requires_confirmation": False
            }

        return {
            "text": "Je n ai pas bien compris votre demande. Vous pouvez me demander le briefing, les alertes, ou les brouillons en attente.",
            "intent": "UNKNOWN", "context_card": None, "ui_action": None, "requires_confirmation": False
        }


    def interact(self, user_query: str) -> Dict[str, Any]:
        """
        Point d entree principal.
        Addendum 4 : Gemini function calling -> execution -> reponse finale.
        Garde-fou de confirmation gere exclusivement cote Python avant tout appel Gemini.
        """
        self._clean_old_history_if_inactive()

        # 1. Verification de confirmation en attente (prioritaire, court-circuite Gemini)
        confirmation_result = self._handle_confirmation_input(user_query)
        if confirmation_result is not None:
            self.conversation_history.append({"role": "Akim", "text": user_query})
            self.conversation_history.append({"role": "Orbe", "text": confirmation_result["text"]})
            if len(self.conversation_history) > 12:
                self.conversation_history = self.conversation_history[-12:]
            return confirmation_result

        # 2. Appel Gemini avec function calling (ou fallback offline)
        result = self._call_gemini_with_tools(user_query)

        # 3. Mise a jour de l historique
        self.conversation_history.append({"role": "Akim", "text": user_query})
        self.conversation_history.append({"role": "Orbe", "text": result["text"]})
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]

        return result

    def respond(self, user_query: str) -> str:
        """Methode de compatibilite retournant directement le texte de reponse."""
        return self.interact(user_query)["text"]
