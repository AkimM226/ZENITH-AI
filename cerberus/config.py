"""
CERBERUS - Configuration & Garde-fous Non-Négociables
Module 1 de ZENITH-SYSTEM
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "cerberus.db"

# Clé API Gemini & Modèle
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Mode Calibration V0 : si True, 100% des messages partent en brouillon pour validation, 0 envoi automatique
CALIBRATION_MODE = os.getenv("CERBERUS_CALIBRATION_MODE", "true").lower() in ("true", "1", "yes")

# Seuil de mots maximal pour un envoi automatique (Section 3.5)
MAX_AUTONOMOUS_WORDS = 150

# Nombre d'échanges consécutifs requis pour passer en Liste Blanche (Section 3.3)
WHITE_LIST_THRESHOLD = 3

# Mots-clés déclencheurs d'alerte OBLIGATOIRE (Section 3.2)
# Bloquent tout envoi automatique, même en liste blanche
ALERT_KEYWORDS = {
    "juridique": [
        "contrat", "clause", "signature", "signer", "engagement formel",
        "responsabilité", "litige", "tribunal", "avocat", "pénalité"
    ],
    "urgence": [
        "urgent", "urgence", "dernier délai", "aujourd'hui même",
        "sinon j'annule", "immédiatement", "asap"
    ],
    "perimetre_etendu": [
        "exclusivité", "partenariat", "investisseur", "investissement",
        "actionnaire", "capital", "filiale", "joint-venture", "consortium"
    ],
    "consulting_hors_offre": [
        "consulting général", "conseil général", "audit général", "consultance générale"
    ]
}

# Grilles tarifaires (Section 5)
TARIFS = {
    "arduino": {
        "nom": "Formation Arduino",
        "prix_reference": 30_000,
        "prix_plancher": 15_000,
        "seuil_groupe": 20,
        "criteres_reduction": [
            "sur_place",          # Structure vient à nous (pas de déplacement)
            "partenaire",         # Technium, université, etc.
            "client_recurrent",    # Client fidèle
            "grand_groupe"        # >= 20 participants
        ]
    },
    "ia_initiation": {
        "nom": "Formation IA — Pack Initiation",
        "prix_reference": 15_000,
        "prix_reduit": 15_000,     # Aucune réduction possible même en groupe
        "reduction_possible": False,
        "format": "2 séances × 2h",
        "max_seances": 2
    },
    "ia_professionnel": {
        "nom": "Formation IA — Pack Professionnel",
        "prix_reference": 30_000,
        "prix_reduit": 25_000,     # Institution >= 10 personnes
        "seuil_reduction": 10,
        "format": "Maximum 3 séances incluses",
        "max_seances": 3,
        # Section 5.2 : Alerte automatique obligatoire, systématique et indépendante du prix
        "alerte_validation_metier_obligatoire": True
    },
    "ia_dev": {
        "nom": "Formation IA — Pack Dev (Vibe Coding)",
        "prix_reference": 30_000,
        "prix_reduit": 27_000,     # Institution >= 10 personnes
        "seuil_reduction": 10,
        "format": "Maximum 3 séances incluses",
        "max_seances": 3
    }
}

# Statuts de contact
STATUS_RED = "ROUGE"      # Institutions, DG Capital du Savoir -> 100% brouillon, 0 envoi auto
STATUS_GREY = "GRISE"     # Nouveaux contacts, statut par défaut
STATUS_WHITE = "BLANCHE"  # Client ayant >= 3 échanges validés sans retouche
