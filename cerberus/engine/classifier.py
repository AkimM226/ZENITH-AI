"""
CERBERUS - Classificateur d'Intention et de Services
Module 1 de ZENITH-SYSTEM
Section 4 du document BRIEFING_CERBERUS_v1.md
"""
import re
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from cerberus.config import GEMINI_API_KEY, GEMINI_MODEL


class ClassificationResult(BaseModel):
    service_id: Optional[str] = None  # 'arduino', 'ia_initiation', 'ia_professionnel', 'ia_dev', 'consulting_general'
    service_name: Optional[str] = None
    confidence: float = 0.0
    detected_price_demand: Optional[int] = None
    participants_count: int = 1
    nb_seances: Optional[int] = None
    criteres_reduction: List[str] = []
    proposes_date: bool = False
    is_tutoiement: bool = False
    summary: str = ""


class IntentClassifier:
    """Classifie les emails entrants selon l'offre de ZENITH AI."""

    SERVICE_PATTERNS = {
        "consulting_general": [
            r"consulting g[ée]n[ée]ral", r"conseil g[ée]n[ée]ral", r"audit g[ée]n[ée]ral",
            r"consultant externe", r"cabinet de conseil", r"strat[ée]gie globale"
        ],
        "arduino": [
            r"arduino", r"[ée]lectronique", r"robotique", r"embarqu[ée]",
            r"kit", r"capteur", r"microcontr[ôo]leur", r"breadboard", r"composants"
        ],
        "ia_initiation": [
            r"d[ée]couvrir l['']ia", r"d[ée]buter", r"prompting", r"bases? de l['']ia",
            r"chatgpt d[ée]butant", r"claude d[ée]butant", r"initiation", r"panorama",
            r"premier pas", r"sensibilisation"
        ],
        "ia_dev": [
            r"vibe coding", r"cr[ée]ation d['']application", r"site web",
            r"d[ée]veloppement avec ia", r"coder avec ia", r"fullstack", r"frontend",
            r"programmation assist[ée]e", r"application mobile", r"d[ée]velopper une app"
        ],
        "ia_professionnel": [
            r"ia appliqu[ée]e", r"usage m[ée]tier", r"formation [ée]quipe",
            r"direction", r"cadres", r"productivit[ée] entreprise", r"finance et ia",
            r"marketing et ia", r"m[ée]tier", r"collaborateurs", r"int[ée]gration ia"
        ]
    }

    NAMES_MAP = {
        "arduino": "Formation Arduino",
        "ia_initiation": "Formation IA — Pack Initiation",
        "ia_professionnel": "Formation IA — Pack Professionnel",
        "ia_dev": "Formation IA — Pack Dev (Vibe Coding)",
        "consulting_general": "Consulting Général (Non disponible)"
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def classify_rule_based(self, content: str, subject: str = "") -> ClassificationResult:
        """Classification robuste déterministe basée sur les expressions régulières."""
        text = f"{subject} {content}".lower()

        scores = {srv: 0 for srv in self.SERVICE_PATTERNS}
        for srv, patterns in self.SERVICE_PATTERNS.items():
            for p in patterns:
                matches = re.findall(p, text)
                scores[srv] += len(matches)

        # Détecter le service ayant le score le plus élevé
        best_service = None
        best_score = 0
        for srv, sc in scores.items():
            if sc > best_score:
                best_score = sc
                best_service = srv

        # Détection du nombre de participants
        participants = 1
        part_match = re.search(r"(\d+)\s*(personnes?|participants?|membres?|collaborateurs?)", text)
        if part_match:
            try:
                participants = int(part_match.group(1))
            except ValueError:
                pass

        # Détection du nombre de séances
        nb_seances = None
        seance_match = re.search(r"(\d+)\s*(s[ée]ances?|sessions?|ateliers?|cours)", text)
        if seance_match:
            try:
                nb_seances = int(seance_match.group(1))
            except ValueError:
                pass

        # Détection d'un prix mentionné
        detected_price = None
        price_match = re.search(r"(\d+[\s\d]*)\s*(fcfa|f cfa|francs?)", text)
        if price_match:
            raw_p = price_match.group(1).replace(" ", "")
            try:
                detected_price = int(raw_p)
            except ValueError:
                pass

        # Détection de proposition de date ferme
        date_patterns = [
            r"d[ée]buter le \d+", r"commencer le \d+", r"lundi prochain", r"mardi prochain",
            r"mercredi prochain", r"la semaine prochaine", r"ce \d+ [a-z]+", r"d[ée]lai de livraison"
        ]
        proposes_date = any(re.search(dp, text) for dp in date_patterns)

        # Détection tutoiement vs vouvoiement
        is_tutoiement = bool(re.search(r"\b(tu|te|toi|ton|ta|tes)\b", text)) and not bool(re.search(r"\b(vous|votre|vos)\b", text))

        # Critères de réduction
        criteres = []
        if participants >= 20:
            criteres.append("grand_groupe")
        if re.search(r"dans vos locaux|sur place|on vient [àa] vous", text):
            criteres.append("sur_place")
        if re.search(r"partenaire|technium|universit[ée]|partenariat", text):
            criteres.append("partenaire")
        if re.search(r"d[ée]j[àa] client|renouveler|continuer", text):
            criteres.append("client_recurrent")

        confidence = 0.85 if best_service and best_score >= 1 else 0.4

        return ClassificationResult(
            service_id=best_service,
            service_name=self.NAMES_MAP.get(best_service) if best_service else "Général / Non classifié",
            confidence=confidence,
            detected_price_demand=detected_price,
            participants_count=participants,
            nb_seances=nb_seances,
            criteres_reduction=criteres,
            proposes_date=proposes_date,
            is_tutoiement=is_tutoiement,
            summary=f"Détection {best_service} (score: {best_score})"
        )

    def classify(self, content: str, subject: str = "") -> ClassificationResult:
        """
        Classifie via Gemini avec repli immédiat sur les règles locales.

        PRINCIPE DE SÉCURITÉ ANTI-HALLUCINATION (inviolable) :
        Gemini peut uniquement enrichir : service_id, service_name, summary.
        Les champs suivants sont TOUJOURS verrouillés sur rule_res (regex déterministe) :
            participants_count, nb_seances, detected_price_demand,
            proposes_date, is_tutoiement, criteres_reduction.
        Raison : ces valeurs alimentent directement le calcul de prix dans rules.py.
        Une hallucination du LLM ne doit JAMAIS pouvoir modifier un montant tarifaire.
        """
        # Étape 1 — Classification déterministe par regex (toujours exécutée en premier)
        rule_res = self.classify_rule_based(content, subject)

        # Étape 2 — Si Gemini n'est pas disponible, résultat déterministe pur
        if not self.client:
            return rule_res

        # Étape 3 — Enrichissement Gemini strictement limité à l'identification du service
        try:
            # Le prompt ne demande QUE les deux champs que Gemini est autorisé à influencer
            prompt = f"""Tu es le classificateur d'intention de l'agent CERBERUS.
Analyse l'email entrant suivant :
Sujet: {subject}
Corps: {content}

Catégories possibles pour service_id :
- 'arduino' (Formation électronique/Arduino)
- 'ia_initiation' (Découverte IA, prompting débutant, 2 séances)
- 'ia_professionnel' (IA appliquée métier, entreprise, cadres)
- 'ia_dev' (Vibe coding, création d'applications / sites)
- 'consulting_general' (Demande de conseil/consulting généraliste)
- null (aucun des services identifié clairement)

Réponds au format JSON avec UNIQUEMENT ces deux clés :
- service_id (string ou null)
- summary (résumé de l'intention en 1-2 phrases)
"""
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)

            # Seuls service_id et summary peuvent être enrichis par Gemini
            gemini_service_id = data.get("service_id") or rule_res.service_id
            gemini_summary = data.get("summary") or rule_res.summary
            gemini_service_name = self.NAMES_MAP.get(gemini_service_id, rule_res.service_name) if gemini_service_id else rule_res.service_name

            # VERROUILLAGE STRICT ANTI-HALLUCINATION :
            # Toutes les données numériques et booléennes qui alimentent rules.py
            # proviennent EXCLUSIVEMENT de rule_res, jamais de la réponse LLM.
            return ClassificationResult(
                # --- Enrichis par Gemini (identification sémantique uniquement) ---
                service_id=gemini_service_id,
                service_name=gemini_service_name,
                confidence=0.95,
                summary=gemini_summary,
                # --- Verrouillés sur la classification déterministe (anti-hallucination) ---
                detected_price_demand=rule_res.detected_price_demand,
                participants_count=rule_res.participants_count,
                nb_seances=rule_res.nb_seances,
                criteres_reduction=rule_res.criteres_reduction,
                proposes_date=rule_res.proposes_date,
                is_tutoiement=rule_res.is_tutoiement,
            )
        except Exception:
            # Repli silencieux et garanti sur le résultat déterministe pur
            return rule_res
