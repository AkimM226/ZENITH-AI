# CERBERUS V1 — Agent Autonome de Gestion Commerciale
**Module 1 du système ZENITH-SYSTEM**

Développé pour Akim (Bobo-Dioulasso, Burkina Faso), basé sur le cahier des charges [BRIEFING_CERBERUS_v1.md](file:///c:/Users/bamba/Downloads/BRIEFING_CERBERUS_v1.md).

---

## 1. Vue d'Ensemble

CERBERUS automatise la gestion commerciale sur le canal email (Gmail) tout en garantissant un niveau de sécurité et de réputation absolu :
- **Principe Fondateur Inviolable :** En cas de doute ou de situation non couverte explicitement par une règle, le comportement par défaut est **toujours l'alerte, jamais l'envoi automatique**.
- **Mode Calibration V0 :** 100% des messages partent en brouillon pour validation par Akim durant la période de rodage.
- **Grille Tarifaire Vérifiable :** Aucune improvisation de prix, respect strict des grilles (Arduino 15k-30k FCFA, IA Initiation 15k FCFA ferme, IA Pro 25k-30k avec alerte métier systématique, IA Dev 27k-30k).
- **Mémoire Relationnelle :** Gestion persistante SQLite des listes Rouge (institutions), Grise (nouveaux contacts) et Blanche (fidèles).
- **Prospection Autonome :** Cibles qualifiées à Bobo-Dioulasso et Ouagadougou, premier contact d'accroche sans prix ferme.
- **Briefing à la Demande :** Synthèse non intrusive consultable à tout moment par Akim pour éviter la fatigue de notification.

---

## 2. Démarrage Rapide

### Dépendances et environnement
Le projet utilise Python 3.14+ et le gestionnaire `uv`.
```bash
python -m uv sync
```

### Commandes CLI principales

```bash
# 1. Consulter le briefing de supervision à la demande
python -m cerberus briefing

# 2. Lancer l'interface web de supervision locale
python -m cerberus ui --port 8000

# 3. Générer un lot de prospects cibles qualifiés (en liste grise)
python -m cerberus prospection

# 4. Simuler l'ingestion d'un message entrant et observer la décision
python -m cerberus simulate --email "client@test.bf" --name "M. Ouedraogo" --subject "Demande formation Arduino" --content "Bonjour, quel est votre tarif pour 25 personnes sur place ?"

# 5. Lancer la suite de tests automatisés
python -m pytest cerberus/tests -v
```

---

## 3. Architecture

- `cerberus/config.py` : Constantes tarifaires, mots-clés d'alerte et seuils.
- `cerberus/engine/rules.py` : Moteur déterministe de règles inviolables.
- `cerberus/engine/classifier.py` : Détecteur d'offres (Arduino, IA Initiation, Pro, Dev).
- `cerberus/engine/drafter.py` : Rédacteur de brouillons conforme au ton et posture.
- `cerberus/engine/pipeline.py` : Orchestrateur central avec journalisation.
- `cerberus/database/` : Persistance relationnelle SQLite (`cerberus.db`).
- `cerberus/modules/prospection.py` : Prospection ciblée Bobo-Dioulasso / Ouaga.
- `cerberus/modules/briefing.py` : Synthèse à la demande.
- `cerberus/ui/` : Serveur FastAPI & Tableau de bord moderne en Dark Mode.
