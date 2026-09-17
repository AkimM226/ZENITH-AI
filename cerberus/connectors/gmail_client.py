"""
CERBERUS - Connecteur Gmail API & Simulateur
Module 1 de ZENITH-SYSTEM
Gère OAuth2, lecture des emails entrants et envoi / création de brouillons
"""
import os
import base64
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    build = None

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.send'
]


class GmailClient:
    """Client officiel Gmail API via OAuth2."""

    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        if not build:
            return

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            elif os.path.exists(self.credentials_path):
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            if creds:
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())

        if creds:
            self.service = build('gmail', 'v1', credentials=creds)

    def is_connected(self) -> bool:
        return self.service is not None

    def fetch_unread_messages(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Récupère les emails non lus de la boîte de réception."""
        if not self.service:
            return []

        try:
            results = self.service.users().messages().list(
                userId='me', q='is:unread label:INBOX', maxResults=max_results
            ).execute()
            messages = results.get('messages', [])
            fetched = []

            for msg in messages:
                msg_data = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                headers = {h['name'].lower(): h['value'] for h in msg_data.get('payload', {}).get('headers', [])}

                # Décodage du corps
                body = ""
                payload = msg_data.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part.get('mimeType') == 'text/plain':
                            data = part.get('body', {}).get('data', '')
                            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            break
                else:
                    data = payload.get('body', {}).get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

                fetched.append({
                    "id": msg['id'],
                    "thread_id": msg.get('threadId'),
                    "from": headers.get('from', ''),
                    "to": headers.get('to', ''),
                    "subject": headers.get('subject', 'Sans sujet'),
                    "date": headers.get('date', ''),
                    "body": body
                })

            return fetched
        except Exception as e:
            print(f"[GmailClient] Erreur lors de la récupération des messages : {e}")
            return []

    def create_draft(self, to: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> bool:
        """Crée un brouillon dans Gmail pour qu'Akim puisse le relire."""
        if not self.service:
            return False

        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            self.service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw}}
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Erreur création de brouillon : {e}")
            return False

    def send_email(self, to: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> bool:
        """Envoie un email via Gmail."""
        if not self.service:
            return False

        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            return True
        except Exception as e:
            print(f"[GmailClient] Erreur envoi email : {e}")
            raise e


class MockGmailClient:
    """Client simulé pour les phases de test, calibration et démonstration sans clé OAuth."""

    def __init__(self):
        self.sent_messages = []
        self.drafted_messages = []
        self.mock_inbox = []

    def add_simulated_email(self, sender: str, subject: str, body: str, message_id: Optional[str] = None):
        self.mock_inbox.append({
            "id": message_id or f"mock-msg-{len(self.mock_inbox) + 1}",
            "from": sender,
            "subject": subject,
            "body": body,
            "date": "2026-09-17 19:30:00"
        })

    def fetch_unread_messages(self, max_results: int = 10) -> List[Dict[str, Any]]:
        messages = list(self.mock_inbox)
        self.mock_inbox.clear()
        return messages

    def create_draft(self, to: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> bool:
        self.drafted_messages.append({"to": to, "subject": subject, "body": body})
        return True

    def send_email(self, to: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> bool:
        self.sent_messages.append({"to": to, "subject": subject, "body": body})
        return True
