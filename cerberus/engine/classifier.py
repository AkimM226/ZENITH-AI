"""
CERBERUS - Classificateur d'Intention et de Services
Module 1 de ZENITH-SYSTEM
Section 4 du document BRIEFING_CERBERUS_v1.md
"""
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from ..config import GEMINI_API_KEY, GEMINI_MODEL


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
            r"d[ée]couvrir l['’]ia", r"d[ée]buter", r"prompting", r"bases? de l['’]ia",
            r"chatgpt d[ée]butant", r"claude d[ée]butant", r"initiation", r"panorama",
            r"premier pas", r"sensibilisation"
        ],
        "ia_dev": [
            r"vibe coding", r"cr[ée]ation d['’]application", r"site web",
            r"d[ée]veloppement avec ia", r"coder avec ia", r"fullstack", r"frontend",
            r"programmation assist[ée]e", r"application mobile", r"d[ée]velopper une app"
        ],
        "ia_professionnel": [
            r"ia appliqu[ée]e", r"usage m[ée]tier", r"formation [ée]quipe",
            r"direction", r"cadres", r"productivit[ée] entreprise", r"finance et ia",
            r"marketing et ia", r"m[ée]tier", r"collaborateurs", r"int[ée]gration ia"
        ]
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
        # Mots caractéristiques du tutoiement
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

        names_map = {
            "arduino": "Formation Arduino",
            "ia_initiation": "Formation IA — Pack Initiation",
            "ia_professionnel": "Formation IA — Pack Professionnel",
            "ia_dev": "Formation IA — Pack Dev (Vibe Coding)",
            "consulting_general": "Consulting Général (Non disponible)"
        }

        confidence = 0.85 if best_service and best_score >= 1 else 0.4

        return ClassificationResult(
            service_id=best_service,
            service_name=names_map.get(best_service) if best_service else "Général / Non classifié",
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
        """Classifie via Gemini avec repli immédiat sur les règles locales."""
        # On exécute la classification par règles
        rule_res = self.classify_rule_based(content, subject)

        # Si le client Gemini n'est pas actif, on retourne le résultat déterministe
        if not self.client:
            return rule_res

        # Enrichissement par Gemini si disponible
        try:
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

Réponds au format JSON avec les clés :
- service_id (string ou null)
- detected_price_demand (entier en FCFA ou null)
- participants_count (entier, défaut 1)
- nb_seances (entier ou null)
- proposes_date (booléen)
- is_tutoiement (booléen)
- summary (court résumé en français)
"""
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            import json
            data = json.loads(response.text)
            srv = data.get("service_id") or rule_res.service_id
            return ClassificationResult(
                service_id=srv,
                service_name=rule_res.service_name if srv == rule_res.service_id else srv,
                confidence=0.95,
                detected_price_demand=data.get("detected_price_demand") or rule_res.detected_price_demand,
                participants_count=data.get("participants_count") or rule_res.participants_count,
                nb_seances=data.get("nb_seances") or rule_res.nb_seances,
                criteres_reduction=rule_res.criteres_reduction,
                proposes_date=bool(data.get("proposes_date") or rule_res.proposes_date),
                is_tutoiement=bool(data.get("is_tutoiement") or rule_res.is_tutoiement),
                summary=data.get("summary") or rule_res.summary
            )
        except Exception:
            # Repli silencieux et garanti sur les règles
            return rule_res
