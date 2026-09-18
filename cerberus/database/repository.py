"""
CERBERUS - Repository (Couche d'accès aux données SQLite)
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from cerberus.config import DB_PATH, STATUS_RED, STATUS_GREY, STATUS_WHITE, WHITE_LIST_THRESHOLD


class Repository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        schema_file = Path(__file__).resolve().parent / "schema.sql"
        with self.get_connection() as conn:
            with open(schema_file, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()

    # --- CONTACTS ---

    def get_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE email = ?", (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["services_interet"] = json.loads(data["services_interet"] or "[]")
                return data
            return None

    def get_or_create_contact(
        self,
        email: str,
        nom: Optional[str] = None,
        organisation: Optional[str] = None,
        is_institution: bool = False,
        is_capital_du_savoir: bool = False
    ) -> Dict[str, Any]:
        email = email.strip().lower()
        contact = self.get_contact_by_email(email)
        if contact:
            return contact

        # Déterminer le statut initial selon les règles du briefing :
        # - Institutions ou Capital du Savoir -> ROUGE
        # - Tout nouveau contact ordinaire -> GRISE
        if is_institution or is_capital_du_savoir or ("capitaldusavoir" in email) or ("gouv." in email) or ("univ-" in email) or ("banque" in email):
            statut = STATUS_RED
            is_institution = True
        else:
            statut = STATUS_GREY

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contacts (email, nom, organisation, statut, is_institution, is_capital_du_savoir)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, nom or email.split("@")[0], organisation or "", statut, 1 if is_institution else 0, 1 if is_capital_du_savoir else 0)
            )
            conn.commit()
            return self.get_contact_by_email(email)

    def update_contact_history(self, contact_id: int, summary_update: str, service_detected: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT historique_resume, services_interet FROM contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            if not row:
                return

            current_hist = row["historique_resume"] or ""
            services = json.loads(row["services_interet"] or "[]")
            if service_detected and service_detected not in services:
                services.append(service_detected)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_hist = f"{current_hist}\n[{now_str}] {summary_update}".strip()

            cursor.execute(
                """
                UPDATE contacts
                SET historique_resume = ?, services_interet = ?, last_contact_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_hist, json.dumps(services), contact_id)
            )
            conn.commit()

    def increment_contact_validation(self, contact_id: int) -> Dict[str, Any]:
        """Incrémente le compteur de validation. Promut en Liste Blanche si seuil atteint et non institution."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Contact non trouvé")

            current_count = row["consecutive_validated_count"] + 1
            new_statut = row["statut"]

            # Si non institution et non Capital du Savoir, promotion possible
            if not row["is_institution"] and not row["is_capital_du_savoir"]:
                if current_count >= WHITE_LIST_THRESHOLD and row["statut"] == STATUS_GREY:
                    new_statut = STATUS_WHITE

            cursor.execute(
                """
                UPDATE contacts
                SET consecutive_validated_count = ?, statut = ?
                WHERE id = ?
                """,
                (current_count, new_statut, contact_id)
            )
            conn.commit()
            return self.get_contact_by_id(contact_id)

    def downgrade_contact(self, contact_id: int, raison: str):
        """Règle de rétrogradation (Section 3.3) : RàZ du compteur en cas de correction lourde ou mécontentement."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE contacts
                SET consecutive_validated_count = 0,
                    statut = CASE WHEN is_institution = 1 OR is_capital_du_savoir = 1 THEN 'ROUGE' ELSE 'GRISE' END,
                    notes = notes || '\n[Rétrogradation] ' || ?
                WHERE id = ?
                """,
                (raison, contact_id)
            )
            conn.commit()

    def get_contact_by_id(self, contact_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["services_interet"] = json.loads(data["services_interet"] or "[]")
                return data
            return None

    def list_contacts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts ORDER BY last_contact_at DESC")
            contacts = []
            for row in cursor.fetchall():
                data = dict(row)
                data["services_interet"] = json.loads(data["services_interet"] or "[]")
                contacts.append(data)
            return contacts

    # --- JOURNAL DE DECISIONS (AUDIT TRAIL) ---

    def log_decision(
        self,
        type_action: str,
        regles_appliquees: List[str] | str,
        resultat: str,
        contact_id: Optional[int] = None,
        email_sujet: Optional[str] = None,
        details: Optional[str] = None
    ) -> int:
        if isinstance(regles_appliquees, list):
            regles_str = "; ".join(regles_appliquees)
        else:
            regles_str = str(regles_appliquees)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO journal_decisions (contact_id, email_sujet, type_action, regles_appliquees, resultat, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (contact_id, email_sujet or "", type_action, regles_str, resultat, details or "")
            )
            conn.commit()
            return cursor.lastrowid

    def list_decision_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT j.*, c.email as contact_email, c.nom as contact_nom
                FROM journal_decisions j
                LEFT JOIN contacts c ON j.contact_id = c.id
                ORDER BY j.timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # --- ALERTES ---

    def create_alert(
        self,
        motif: str,
        contexte_email: str,
        contact_id: Optional[int] = None,
        niveau: str = "STANDARD"
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alertes (contact_id, niveau, motif, contexte_email, statut)
                VALUES (?, ?, ?, ?, 'EN_ATTENTE')
                """,
                (contact_id, niveau, motif, contexte_email)
            )
            conn.commit()
            return cursor.lastrowid

    def list_pending_alerts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, c.email as contact_email, c.nom as contact_nom, c.statut as contact_statut
                FROM alertes a
                LEFT JOIN contacts c ON a.contact_id = c.id
                WHERE a.statut = 'EN_ATTENTE'
                ORDER BY CASE WHEN a.niveau = 'URGENT' THEN 1 ELSE 2 END, a.timestamp DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def resolve_alert(self, alert_id: int, notes: str = "Résolue par Akim"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE alertes
                SET statut = 'TRAITEE', resolution_notes = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (notes, alert_id)
            )
            conn.commit()

    # --- BROUILLONS ---

    def create_draft(
        self,
        contact_id: int,
        email_sujet: str,
        email_destinataire: str,
        corps_propose: str,
        motif_blocage: str,
        message_id_source: Optional[str] = None,
        texte_original_client: Optional[str] = None
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO brouillons (contact_id, message_id_source, email_sujet, email_destinataire, corps_propose, motif_blocage, statut, texte_original_client)
                VALUES (?, ?, ?, ?, ?, ?, 'A_VALIDER', ?)
                """,
                (contact_id, message_id_source, email_sujet, email_destinataire, corps_propose, motif_blocage, texte_original_client)
            )
            conn.commit()
            return cursor.lastrowid

    def list_pending_drafts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.*, c.nom as contact_nom, c.statut as contact_statut, c.consecutive_validated_count
                FROM brouillons b
                JOIN contacts c ON b.contact_id = c.id
                WHERE b.statut = 'A_VALIDER'
                ORDER BY b.created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def validate_draft(self, draft_id: int, modified_body: Optional[str] = None) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM brouillons WHERE id = ?", (draft_id,))
            draft = cursor.fetchone()
            if not draft:
                raise ValueError("Brouillon introuvable")

            was_modified = modified_body is not None and modified_body.strip() != draft["corps_propose"].strip()
            new_statut = "MODIFIE_ENVOYE" if was_modified else "VALIDE_ENVOYE"

            cursor.execute(
                """
                UPDATE brouillons
                SET statut = ?, corps_modifie = ?, validated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_statut, modified_body if was_modified else None, draft_id)
            )
            conn.commit()

            # Mise à jour du compteur de contact selon la règle de fidélisation/rétrogradation
            contact_id = draft["contact_id"]
            if was_modified:
                # Si modification lourde -> rétrogradation
                self.downgrade_contact(contact_id, "Correction manuelle requise sur le brouillon par Akim")
            else:
                # Si validé sans modification -> incrément de confiance
                self.increment_contact_validation(contact_id)

            return dict(draft)

    def reject_draft(self, draft_id: int, raison: str = "Rejeté par Akim"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE brouillons SET statut = 'REJETE', corps_modifie = ? WHERE id = ?",
                (f"REJET: {raison}", draft_id)
            )
            conn.commit()

    def get_draft_full_context(self, draft_id: int) -> Optional[Dict[str, Any]]:
        """Récupère le contexte complet d'un brouillon, y compris le texte original du client (Addendum 6)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT b.*, c.nom as contact_nom, c.email as contact_email, c.statut as contact_statut
                FROM brouillons b
                JOIN contacts c ON b.contact_id = c.id
                WHERE b.id = ?
                """,
                (draft_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_draft_body_temp(self, draft_id: int, new_body: str) -> bool:
        """Met à jour provisoirement le corps d'un brouillon (Addendum 6 - edit_draft)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE brouillons SET corps_propose = ? WHERE id = ?",
                (new_body, draft_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    # --- PROSPECTS ---

    def create_prospect(
        self,
        nom: str,
        organisation: str,
        secteur: str,
        source: str,
        premier_message: str,
        email: Optional[str] = None,
        telephone: Optional[str] = None,
        ville: str = "Bobo-Dioulasso"
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO prospects (nom, organisation, secteur, source, premier_message, email, telephone, ville)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (nom, organisation, secteur, source, premier_message, email, telephone, ville)
            )
            conn.commit()
            return cursor.lastrowid

    def list_prospects(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM prospects ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- BRIEFING METRICS ---

    def get_briefing_data(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Alertes en attente
            cursor.execute("SELECT COUNT(*) FROM alertes WHERE statut = 'EN_ATTENTE'")
            total_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alertes WHERE statut = 'EN_ATTENTE' AND niveau = 'URGENT'")
            urgent_alerts = cursor.fetchone()[0]

            # Brouillons en attente
            cursor.execute("SELECT COUNT(*) FROM brouillons WHERE statut = 'A_VALIDER'")
            pending_drafts = cursor.fetchone()[0]

            # Actions auto vs alertes du journal
            cursor.execute("SELECT resultat, COUNT(*) as cnt FROM journal_decisions GROUP BY resultat")
            actions_summary = {row["resultat"]: row["cnt"] for row in cursor.fetchall()}

            # Dernières alertes urgentes
            cursor.execute(
                """
                SELECT a.*, c.nom, c.email
                FROM alertes a
                LEFT JOIN contacts c ON a.contact_id = c.id
                WHERE a.statut = 'EN_ATTENTE' AND a.niveau = 'URGENT'
                ORDER BY a.timestamp DESC LIMIT 5
                """
            )
            urgent_list = [dict(r) for r in cursor.fetchall()]

            # Taux de validation sans retouche (indicateur de suivi section 10)
            cursor.execute("SELECT COUNT(*) FROM brouillons WHERE statut = 'VALIDE_ENVOYE'")
            valide_sans_modif = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM brouillons WHERE statut IN ('VALIDE_ENVOYE', 'MODIFIE_ENVOYE')")
            total_traites = cursor.fetchone()[0]
            taux_fiabilite = round((valide_sans_modif / total_traites * 100), 1) if total_traites > 0 else 100.0

            return {
                "total_alerts": total_alerts,
                "urgent_alerts": urgent_alerts,
                "pending_drafts": pending_drafts,
                "actions_summary": actions_summary,
                "urgent_list": urgent_list,
                "taux_fiabilite": taux_fiabilite,
                "total_brouillons_traites": total_traites
            }
