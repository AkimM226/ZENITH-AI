"""
CERBERUS VOX - Module de Reconnaissance Vocale (STT) Locale
Section 4 du document ADDENDUM_2_ORBE_INTERFACE.md
Utilise Faster-Whisper pour une transcription 100% locale, gratuite et hors-ligne.
"""
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class VoxSTT:
    """Moteur de reconnaissance vocale Speech-to-Text local."""

    def __init__(self, model_size: str = "tiny"):
        """
        Initialise le modèle Whisper local.
        Modèle par défaut : 'tiny' (39 Mo, ultra-rapide sur CPU standard).
        Peut être configuré en 'base' ou 'small' selon les performances du PC.
        """
        self.model_size = model_size
        self.model = None
        self._is_loaded = False

    def _ensure_model_loaded(self):
        """Charge le modèle en mémoire de manière paresseuse au premier besoin."""
        if not self._is_loaded and WhisperModel is not None:
            try:
                # Exécution sur CPU avec quantification int8 pour vitesse maximale sans GPU
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
        """Transcrit un fichier audio (WAV, MP3, OGG, WEBM) en texte."""
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
                vad_filter=True  # Filtre le silence automatiquement
            )
            text_parts = [segment.text.strip() for segment in segments]
            return " ".join(text_parts).strip()
        except Exception as e:
            print(f"[!] Erreur transcription audio : {e}")
            return ""
