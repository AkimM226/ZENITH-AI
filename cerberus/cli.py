import sys
import time
import signal
import argparse
from datetime import datetime
from typing import Optional
import uvicorn


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


def cmd_app(args):
    """Lance l'application Desktop native avec l'Orbe de présence (Addendum 2)."""
    try:
        from .ui.desktop import run_desktop_app
        run_desktop_app(host=args.host, port=args.port, start_omnipresent=args.omnipresent)
    except Exception as e:
        print(f"[!] Erreur au lancement de l'application Desktop : {e}")


def cmd_prospection(args):
    repo = Repository()
    engine = ProspectionEngine(repo)
    print(f"[*] Module de Prospection Sécurisé CERBERUS")
    if args.file:
        print(f"    Source des prospects : {args.file}")
    else:
        print(f"    Source par défaut : data/prospects.json")

    batch = engine.generate_prospects_batch(file_path=args.file)
    if not batch:
        print("[!] Aucun prospect traité. Veuillez renseigner un fichier JSON valide (ex: data/prospects.example.json).")
        return

    print(f"[+] {len(batch)} prospect(s) qualifié(s) généré(s) et placé(s) en Liste Grise :")
    for p in batch:
        print(f"  - {p['nom']} ({p['organisation']}) [{p['secteur']}] -> {p.get('email')}")
        print(f"    Message d'accroche sans prix ferme préparé pour validation.")


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


def run_worker_cycle(repo: Repository, client, pipeline: CerberusPipeline) -> int:
    """Exécute un cycle unique de relève et traitement d'emails."""
    messages = client.fetch_unread_messages()
    count = len(messages)
    for msg in messages:
        sender = msg.get("from", "inconnu@example.com")
        subject = msg.get("subject", "")
        body = msg.get("body", "")
        res = pipeline.process_incoming_email(
            sender_email=sender,
            subject=subject,
            content=body,
            message_id=msg.get("id")
        )
        print(f"    [{datetime.now().strftime('%H:%M:%S')}] '{subject}' -> Décision : {res['decision']}")
    return count


def cmd_worker(args):
    repo = Repository()
    client = GmailClient()
    pipeline = CerberusPipeline(repo=repo, email_sender=client if client.is_connected() else None)

    if client.is_connected():
        print("[+] Connecté à Gmail API. En attente d'emails réels...")
    else:
        print("[!] Gmail API non configuré (token.json absent). Mode MockGmailClient actif.")
        client = MockGmailClient()

    count = run_worker_cycle(repo, client, pipeline)
    print(f"[*] Cycle terminé : {count} message(s) traité(s).")


def cmd_daemon(args):
    """
    Mode service continu de surveillance des emails entrants (Section 2.2 Addendum V1).
    Tourne en boucle avec un intervalle configurable jusqu'à réception de Ctrl+C.
    """
    repo = Repository()
    dry_run = getattr(args, "dry_run", False)
    interval = getattr(args, "interval", 120)

    if dry_run:
        print(f"[!] Démarrage CERBERUS DAEMON en MODE SIMULATION (MockGmailClient)")
        client = MockGmailClient()
    else:
        client = GmailClient()
        if client.is_connected():
            print(f"[+] Démarrage CERBERUS DAEMON connecté à Gmail API réel")
        else:
            print(f"[!] Gmail API non configuré. Repli automatique sur MockGmailClient.")
            client = MockGmailClient()

    pipeline = CerberusPipeline(repo=repo, email_sender=client if client.is_connected() else None)

    print(f"[*] Surveillance continue active (cycle toutes les {interval} secondes).")
    print(f"[*] Appuyez sur Ctrl+C pour arrêter le service proprement.\n")

    cycle_num = 0
    try:
        while True:
            cycle_num += 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"--- [Cycle #{cycle_num} | {now_str}] Relève des emails...")
            try:
                processed = run_worker_cycle(repo, client, pipeline)
                if processed == 0:
                    print(f"    Aucun nouvel email non lu.")
            except Exception as e:
                print(f"    [!] Erreur lors de la relève du cycle #{cycle_num} : {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n[!] Signal d'arrêt reçu (Ctrl+C). Arrêt propre du démon CERBERUS.")
        print(f"[*] Total cycles exécutés : {cycle_num}. Base de données intacte. Au revoir.")


def cmd_vox(args):
    """Lance l'assistant vocal local VOX pour Akim (Section 3 Addendum V1)."""
    try:
        from .vox.engine import VoxEngine
    except ImportError as e:
        print(f"[!] Le module VOX nécessite des dépendances audio : {e}")
        return

    vox = VoxEngine(
        wake_word=args.wake_word,
        ptt_mode=args.ptt,
        voice_gender=args.voice
    )
    vox.run()


def main():
    # Support UTF-8 sur terminal Windows interactif
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="CERBERUS V1 — Agent Commercial Autonome")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Briefing
    p_briefing = subparsers.add_parser("briefing", help="Afficher le briefing de supervision à la demande")
    p_briefing.set_defaults(func=cmd_briefing)

    # UI (mode navigateur)
    p_ui = subparsers.add_parser("ui", help="Lancer l'interface web dans le navigateur")
    p_ui.add_argument("--host", default="127.0.0.1", help="Adresse IP d'écoute")
    p_ui.add_argument("--port", type=int, default=8000, help="Port d'écoute")
    p_ui.add_argument("--reload", action="store_true", help="Rechargement à chaud")
    p_ui.set_defaults(func=cmd_ui)

    # App Desktop Orbe (application native Windows PyWebView)
    p_app = subparsers.add_parser("app", help="Lancer l'application Desktop native (Orbe de présence)")
    p_app.add_argument("--host", default="127.0.0.1", help="Adresse IP d'écoute")
    p_app.add_argument("--port", type=int, default=8000, help="Port d'écoute")
    p_app.add_argument("--omnipresent", action="store_true", help="Démarrer directement en mode omniprésent flottant")
    p_app.set_defaults(func=cmd_app)

    # Prospection
    p_prospect = subparsers.add_parser("prospection", help="Générer un lot de prospects cibles qualifiés")
    p_prospect.add_argument("--file", default=None, help="Chemin vers un fichier JSON de prospects réels")
    p_prospect.set_defaults(func=cmd_prospection)

    # Simulation
    p_sim = subparsers.add_parser("simulate", help="Simuler l'ingestion d'un message")
    p_sim.add_argument("--email", required=True, help="Email expéditeur")
    p_sim.add_argument("--name", default="Contact Test", help="Nom expéditeur")
    p_sim.add_argument("--subject", required=True, help="Sujet du message")
    p_sim.add_argument("--content", required=True, help="Corps du message")
    p_sim.set_defaults(func=cmd_simulate)

    # Worker (cycle unique)
    p_worker = subparsers.add_parser("worker", help="Relever les emails non lus une fois et les traiter")
    p_worker.set_defaults(func=cmd_worker)

    # Daemon (surveillance continue)
    p_daemon = subparsers.add_parser("daemon", help="Exécuter la surveillance des emails en continu")
    p_daemon.add_argument("--interval", type=int, default=120, help="Intervalle en secondes entre chaque relève (défaut: 120)")
    p_daemon.add_argument("--dry-run", action="store_true", help="Exécuter en mode simulation sans modifier la boîte réelle")
    p_daemon.set_defaults(func=cmd_daemon)

    # VOX (Assistant Vocal Local)
    p_vox = subparsers.add_parser("vox", help="Démarrer l'assistant vocal local VOX pour Akim")
    p_vox.add_argument("--wake-word", default="cerberus", choices=["cerberus", "zenith"], help="Mot-clé d'activation vocale")
    p_vox.add_argument("--ptt", action="store_true", help="Mode Push-to-Talk (touche Entrée) au lieu du micro passif continu")
    p_vox.add_argument("--voice", default="male", choices=["male", "female"], help="Voix de synthèse (male: Henri, female: Denise)")
    p_vox.set_defaults(func=cmd_vox)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
