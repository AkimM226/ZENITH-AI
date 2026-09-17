"""
CERBERUS VOX - Moteur d'Exécution de l'Assistant Vocal
Section 3 & 4 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md
"""
import sys
from typing import Optional
from cerberus.vox.tts import VoxTTS
from cerberus.vox.assistant import VoxAssistant


class VoxEngine:
    """Orchestre les interactions vocales locales avec Akim."""

    def __init__(
        self,
        wake_word: str = "cerberus",
        ptt_mode: bool = False,
        voice_gender: str = "male"
    ):
        self.wake_word = wake_word.lower()
        self.ptt_mode = ptt_mode
        self.tts = VoxTTS(voice_gender=voice_gender)
        self.assistant = VoxAssistant()

    def run(self):
        """Lance la boucle d'interaction avec Akim."""
        print("=" * 65)
        print("  🎙️  CERBERUS VOX — Assistant Vocal Local (ZENITH AI)")
        print(f"  Mot d'activation : '{self.wake_word}' | Voix : {self.tts.voice}")
        print("  Usage réservé : Consultation et supervision pour Akim")
        print("  Tapez 'exit' ou Ctrl+C pour quitter.")
        print("=" * 65 + "\n")

        # Message d'accueil oral
        welcome_text = "Bonjour Akim. CERBERUS VOX est à votre écoute."
        print(f"[VOX] {welcome_text}")
        try:
            self.tts.speak(welcome_text, play_audio=True)
        except Exception as e:
            print(f"[!] Lecture audio indisponible : {e}")

        while True:
            try:
                print(f"\n[Akim ({self.wake_word})] > ", end="", flush=True)
                query = sys.stdin.readline()
                if not query:
                    break

                query = query.strip()
                if not query:
                    continue

                if query.lower() in ["exit", "quit", "quitter"]:
                    farewell = "À bientôt, Akim. CERBERUS reste en veille."
                    print(f"[VOX] {farewell}")
                    try:
                        self.tts.speak(farewell, play_audio=True)
                    except Exception:
                        pass
                    break

                # Traitement par l'assistant
                response = self.assistant.respond(query)
                print(f"[VOX] {response}")

                # Synthèse orale
                try:
                    self.tts.speak(response, play_audio=True)
                except Exception as e:
                    print(f"[!] (Audio non joué : {e})")

            except KeyboardInterrupt:
                print("\n[!] Arrêt de VOX demandé par Ctrl+C. Au revoir Akim.")
                break
