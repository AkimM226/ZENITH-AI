"""
CERBERUS VOX - Module de Synthèse Vocale (TTS)
Utilise Edge-TTS (voix neuronales gratuites en français).
Section 3.2 & 4.3 du document ADDENDUM_CERBERUS_V1_AUDIT_ET_VOX.md
"""
import os
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None


class VoxTTS:
    """Moteur de synthèse vocale neuronale gratuite en français."""

    VOICES = {
        "male": "fr-FR-HenriNeural",       # Voix masculine posée et claire
        "female": "fr-FR-DeniseNeural",    # Voix féminine naturelle
    }

    def __init__(self, voice_gender: str = "male"):
        self.voice = self.VOICES.get(voice_gender, self.VOICES["male"])
        self.cache_dir = Path("data") / "audio"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _generate_audio_async(self, text: str, output_file: Path) -> Path:
        """Génère un fichier audio MP3 via Edge-TTS."""
        if not edge_tts:
            raise RuntimeError("Le package edge-tts n'est pas disponible dans l'environnement.")

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(output_file))
        return output_file

    async def synthesize_async(self, text: str, filename: Optional[str] = None) -> Path:
        """Génère le fichier MP3 de manière asynchrone (pour FastAPI)."""
        if not filename:
            import uuid
            filename = f"vox_{uuid.uuid4().hex[:8]}.mp3"

        out_path = self.cache_dir / filename
        await self._generate_audio_async(text, out_path)
        return out_path

    def synthesize(self, text: str, filename: Optional[str] = None) -> Path:
        """Génère le fichier MP3 de manière synchrone."""
        return asyncio.run(self.synthesize_async(text, filename))

    def play(self, audio_path: Path):
        """Lit un fichier audio sous Windows."""
        abs_path = Path(audio_path).resolve()
        if not abs_path.exists():
            return

        # Sous Windows : lecture via Windows Media Player en mode silencieux ou script PowerShell
        ps_script = f"""
Add-Type -AssemblyName presentationCore
$player = New-Object system.windows.media.mediaplayer
$player.open([System.Uri]'{str(abs_path)}')
$player.Play()
Start-Sleep -Milliseconds 300
while ($player.NaturalDuration.HasTimeSpan -and ($player.Position -lt $player.NaturalDuration.TimeSpan)) {{
    Start-Sleep -Milliseconds 200
}}
Start-Sleep -Milliseconds 400
$player.Close()
"""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30
            )
        except Exception:
            pass

    def speak(self, text: str, play_audio: bool = True) -> Path:
        """Synthétise le texte et le lit à voix haute."""
        # Nettoyage léger des balises pour une lecture orale fluide
        clean_text = text.replace("**", "").replace("*", "").replace("#", "").strip()
        audio_file = self.synthesize(clean_text)
        if play_audio:
            self.play(audio_file)
        return audio_file
