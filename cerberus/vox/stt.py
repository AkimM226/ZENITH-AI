"""
CERBERUS VOX - Module de Reconnaissance Vocale (STT) Locale
Section 4 du document ADDENDUM_2_ORBE_INTERFACE.md
Addendum 4 : Passage a Whisper 'small' + seuil anti-hallucination.
Utilise Faster-Whisper pour une transcription 100% locale, gratuite et hors-ligne.
"""
from pathlib import Path
from typing import Union

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class VoxSTT:
    """Moteur de reconnaissance vocale Speech-to-Text local."""

    def __init__(self, model_size: str = "small"):
        """
        Initialise le modele Whisper local.
        Modele par defaut : 'small' (244 Mo, meilleur compromis precision/vitesse pour le francais).
        - 'tiny' : ultra-rapide mais prone aux hallucinations sur fragments courts.
        - 'small' : recommande pour le francais, robuste aux silences et bruits de fond.
        - 'base' : intermediaire si 'small' est trop lent sur CPU tres contraint.
        ATTENTION : le modele est telecharge automatiquement au premier lancement si absent du cache.
        """
        self.model_size = model_size
        self.model = None
        self._is_loaded = False

    def _ensure_model_loaded(self):
        """Charge le modele en memoire de maniere paresseuse au premier besoin."""
        if not self._is_loaded and WhisperModel is not None:
            try:
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                self._is_loaded = True
            except Exception as e:
                print(f"[!] Erreur initialisation Faster-Whisper : {e}")
                self.model = None

    def transcribe_file(self, audio_path: Union[str, Path], language: str = "fr") -> str:
        """Transcrit un fichier audio (WAV, MP3, OGG, WEBM) en texte.

        Mesures anti-hallucination (Addendum 4) :
        - no_speech_threshold=0.6 : rejette les segments detectes comme silence/bruit
        - vad_filter=True : filtre le silence automatiquement
        - condition_on_previous_text=False : evite la propagation d hallucinations inter-segments
        - Post-check : si audio < 1.5s et resultat <= 2 mots, retourne vide
        """
        self._ensure_model_loaded()
        if not self.model:
            return ""

        path_obj = Path(audio_path)
        if not path_obj.exists():
            return ""

        try:
            segments, info = self.model.transcribe(
                str(path_obj),
                language=language,
                beam_size=3,
                vad_filter=True,
                no_speech_threshold=0.6,
                condition_on_previous_text=False
            )
            text_parts = [segment.text.strip() for segment in segments]
            result = " ".join(text_parts).strip()

            # Garde-fou post-transcription (Addendum 4)
            audio_duration = getattr(info, "duration", None)
            if audio_duration is not None and audio_duration < 1.5:
                word_count = len(result.split()) if result else 0
                if word_count <= 2:
                    return ""

            return result
        except Exception as e:
            print(f"[!] Erreur transcription audio : {e}")
            return ""
