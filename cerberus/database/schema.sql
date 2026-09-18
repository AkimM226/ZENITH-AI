-- Schéma SQLite pour CERBERUS (Module 1 ZENITH-SYSTEM)

-- 1. Table des contacts (Mémoire relationnelle persistante)
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    nom TEXT,
    organisation TEXT,
    statut TEXT NOT NULL DEFAULT 'GRISE', -- 'ROUGE', 'GRISE', 'BLANCHE'
    is_institution BOOLEAN DEFAULT 0,
    is_capital_du_savoir BOOLEAN DEFAULT 0,
    consecutive_validated_count INTEGER DEFAULT 0,
    counter_proposal_count INTEGER DEFAULT 0,
    services_interet TEXT DEFAULT '[]', -- JSON list de services
    historique_resume TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_contact_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Journal de décisions (Traçabilité & Audit permanent)
CREATE TABLE IF NOT EXISTS journal_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contact_id INTEGER,
    email_sujet TEXT,
    type_action TEXT NOT NULL, -- 'CLASSIFICATION', 'BROUILLON', 'ENVOI_AUTO', 'ALERTE'
    regles_appliquees TEXT NOT NULL, -- JSON list ou description textuelle des règles
    resultat TEXT NOT NULL, -- 'ENVOYE', 'MIS_EN_ATTENTE_BROUILLON', 'ALERTE_DECLENCHEE'
    details TEXT,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

-- 3. File d'attente des alertes pour Akim
CREATE TABLE IF NOT EXISTS alertes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    niveau TEXT NOT NULL DEFAULT 'STANDARD', -- 'URGENT', 'STANDARD'
    motif TEXT NOT NULL,
    contexte_email TEXT,
    statut TEXT NOT NULL DEFAULT 'EN_ATTENTE', -- 'EN_ATTENTE', 'TRAITEE', 'IGNORE'
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

-- 4. Brouillons de réponses à valider
CREATE TABLE IF NOT EXISTS brouillons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    message_id_source TEXT,
    email_sujet TEXT NOT NULL,
    email_destinataire TEXT NOT NULL,
    corps_propose TEXT NOT NULL,
    corps_modifie TEXT,
    motif_blocage TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'A_VALIDER', -- 'A_VALIDER', 'VALIDE_ENVOYE', 'MODIFIE_ENVOYE', 'REJETE'
    texte_original_client TEXT, -- Texte intégral du message original du client (Addendum 6)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

-- 5. Module de Prospection
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    organisation TEXT NOT NULL,
    secteur TEXT NOT NULL,
    ville TEXT DEFAULT 'Bobo-Dioulasso',
    email TEXT UNIQUE,
    telephone TEXT,
    source TEXT NOT NULL,
    premier_message TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'A_VALIDER', -- 'A_VALIDER', 'CONTACTE', 'REPONDU', 'CONVERTI', 'ABANDONNE'
    relances_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_action_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour les recherches rapides
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_alertes_statut ON alertes(statut);
CREATE INDEX IF NOT EXISTS idx_brouillons_statut ON brouillons(statut);
CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON journal_decisions(timestamp);
