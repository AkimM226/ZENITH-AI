import sys
import argparse
import uvicorn
from typing import Optional

# Support UTF-8 sur Windows
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


from .database.repository import Repository
from .modules.briefing import BriefingSynthesizer
from .modules.prospection import ProspectionEngine
from .engine.pipeline import CerberusPipeline
from .connectors.gmail_client import GmailClient, MockGmailClient


def cmd_briefing(args):
    repo = Repository()
    synth = BriefingSynthesizer(repo)
    briefing = synth.generate_briefing()
    print(briefing["formatted_text"])


def cmd_ui(args):
    print(f"[*] Démarrage de l'interface de supervision CERBERUS sur http://{args.host}:{args.port}")
    uvicorn.run("cerberus.ui.server:app", host=args.host, port=args.port, reload=args.reload)


def cmd_prospection(args):
    repo = Repository()
    engine = ProspectionEngine(repo)
    print("[*] Lancement du module de prospection autonome (Bobo & Ouaga)...")
    batch = engine.generate_prospects_batch()
    print(f"[+] {len(batch)} prospects qualifiés générés et placés en Liste Grise :")
    for p in batch:
        print(f"  - {p['nom']} ({p['organisation']}) [{p['secteur']}]")
        print(f"    Message d'accroche sans prix ferme généré.")


def cmd_simulate(args):
    repo = Repository()
    pipeline = CerberusPipeline(repo=repo)

    print(f"[*] Simulation d'ingestion d'email entrant :")
    print(f"    Expéditeur : {args.name} <{args.email}>")
    print(f"    Sujet      : {args.subject}")
    print(f"    Message    :\n{args.content}\n")

    result = pipeline.process_incoming_email(
        sender_email=args.email,
        sender_name=args.name,
        subject=args.subject,
        content=args.content
    )

    print(f"===> DÉCISION CERBERUS : [{result['decision']}]")
    eval_info = result["evaluation"]
    if eval_info["is_alert"]:
        print(f"    🚨 ALERTE Déclenchée (Niveau {eval_info['urgency']})")
        print(f"    Motifs : {eval_info['reasons']}")
    else:
        print(f"    🛡️ Raison retenue / statut : {eval_info['reasons']}")

    print(f"    Règles appliquées : {eval_info['applied_rules']}")
    if eval_info.get("suggested_price"):
        print(f"    Tarif calculé : {eval_info['suggested_price']:,} FCFA")

    print(f"\n[PROPOSITION DE RÉPONSE] :\n{result['generated_reply']}")


def cmd_worker(args):
    repo = Repository()
    client = GmailClient()
    pipeline = CerberusPipeline(repo=repo, email_sender=client if client.is_connected() else None)

    if client.is_connected():
        print("[+] Connecté à Gmail API. En attente d'emails réels...")
    else:
        print("[!] Gmail API non configuré (token.json absent). Mode MockGmailClient actif.")
        client = MockGmailClient()

    messages = client.fetch_unread_messages()
    print(f"[*] {len(messages)} message(s) non lu(s) trouvé(s).")
    for msg in messages:
        sender = msg.get("from", "inconnu@example.com")
        subject = msg.get("subject", "")
        body = msg.get("body", "")
        res = pipeline.process_incoming_email(sender_email=sender, subject=subject, content=body, message_id=msg.get("id"))
        print(f"    Traite '{subject}' -> Décision : {res['decision']}")


def main():
    parser = argparse.ArgumentParser(description="CERBERUS V1 — Agent Commercial Autonome")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Briefing
    p_briefing = subparsers.add_parser("briefing", help="Afficher le briefing de supervision à la demande")
    p_briefing.set_defaults(func=cmd_briefing)

    # UI
    p_ui = subparsers.add_parser("ui", help="Lancer le tableau de bord web local")
    p_ui.add_argument("--host", default="127.0.0.1", help="Adresse IP d'écoute")
    p_ui.add_argument("--port", type=int, default=8000, help="Port d'écoute")
    p_ui.add_argument("--reload", action="store_true", help="Rechargement à chaud")
    p_ui.set_defaults(func=cmd_ui)

    # Prospection
    p_prospect = subparsers.add_parser("prospection", help="Générer un lot de prospects cibles qualifiés")
    p_prospect.set_defaults(func=cmd_prospection)

    # Simulation
    p_sim = subparsers.add_parser("simulate", help="Simuler l'ingestion d'un message")
    p_sim.add_argument("--email", required=True, help="Email expéditeur")
    p_sim.add_argument("--name", default="Contact Test", help="Nom expéditeur")
    p_sim.add_argument("--subject", required=True, help="Sujet du message")
    p_sim.add_argument("--content", required=True, help="Corps du message")
    p_sim.set_defaults(func=cmd_simulate)

    # Worker
    p_worker = subparsers.add_parser("worker", help="Relever les emails non lus et les traiter")
    p_worker.set_defaults(func=cmd_worker)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
