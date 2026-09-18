"""
CERBERUS - Serveur Web & API de l'Interface Orbe Desktop
Module 1 de ZENITH-SYSTEM
Addendum 2 (Interface Orbe & Mode Omniprésent)
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from cerberus.database.repository import Repository
from cerberus.modules.briefing import BriefingSynthesizer
from cerberus.modules.prospection import ProspectionEngine
from cerberus.engine.pipeline import CerberusPipeline
from cerberus.vox.assistant import VoxAssistant
from cerberus.vox.tools import VoxDataTools
from cerberus.vox.tts import VoxTTS
from cerberus.vox.stt import VoxSTT
from cerberus.config import CALIBRATION_MODE


app = FastAPI(
    title="CERBERUS ORBE - ZENITH AI",
    description="Interface de présence conversationnelle pour Akim"
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_CACHE_DIR = Path("data") / "audio"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Instances partagées
repo = Repository()
briefing_synth = BriefingSynthesizer(repo)
prospection_engine = ProspectionEngine(repo)
pipeline = CerberusPipeline(repo=repo)
data_tools = VoxDataTools(repo=repo)
assistant = VoxAssistant(data_tools=data_tools)
tts = VoxTTS(voice_gender="male")
stt = VoxSTT(model_size="tiny")


class ChatQuery(BaseModel):
    query: str


# --- ROUTES PRINCIPALES (Addendum 2) ---

@app.get("/", response_class=HTMLResponse)
async def orbe_interface(request: Request):
    """
    Interface par défaut : Présence unique de l'Orbe (Section 1 de l'Addendum 2).
    Aucune liste permanente, dialogue fluide au centre de l'expérience.
    """
    return templates.TemplateResponse(
        request=request,
        name="orbe.html",
        context={
            "calibration_mode": CALIBRATION_MODE,
            "title": "CERBERUS — Présence Orbe"
        }
    )


@app.get("/manual", response_class=HTMLResponse)
async def manual_dashboard(request: Request):
    """
    Mode manuel classique (Section 6 de l'Addendum 2).
    Accès secondaire cliquable sur demande explicite pour valider/consulter en masse.
    """
    briefing = briefing_synth.generate_briefing()
    pending_alerts = repo.list_pending_alerts()
    pending_drafts = repo.list_pending_drafts()
    contacts = repo.list_contacts()
    decision_logs = repo.list_decision_logs(limit=25)
    prospects = repo.list_prospects()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "briefing": briefing,
            "pending_alerts": pending_alerts,
            "pending_drafts": pending_drafts,
            "contacts": contacts,
            "decision_logs": decision_logs,
            "prospects": prospects,
            "calibration_mode": CALIBRATION_MODE
        }
    )


# --- ENDPOINTS ORBE CONVERSATIONNELLE & AUDIO ---

@app.post("/api/vox/interact")
async def vox_interact(data: ChatQuery):
    """
    Point de convergence unique voix / texte :
    Traite la requête, génère la voix neuronale, et renvoie les cartes contextuelles.
    """
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Requête vide.")

    # 1. Traitement par l'assistant conversationnel
    result = assistant.interact(query)
    response_text = result["text"]

    # 2. Synthèse vocale neuronale Edge-TTS en français
    audio_url = None
    try:
        audio_file = await tts.synthesize_async(response_text)
        audio_url = f"/api/vox/audio/{audio_file.name}"
    except Exception as e:
        print(f"[!] Erreur synthèse Edge-TTS : {e}")

    # 3. Réponse complète pour l'Orbe
    return {
        "text": response_text,
        "audio_url": audio_url,
        "intent": result["intent"],
        "context_card": result["context_card"],
        "ui_action": result["ui_action"],
        "requires_confirmation": result["requires_confirmation"]
    }


@app.post("/api/vox/transcribe")
async def vox_transcribe(audio: UploadFile = File(...)):
    """
    Reçoit le fragment audio capté par le microphone et le transcrit localement via Faster-Whisper.
    """
    try:
        suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            shutil.copyfileobj(audio.file, tmp)

        text = stt.transcribe_file(tmp_path, language="fr")
        try:
            tmp_path.unlink()
        except Exception:
            pass

        return {"transcription": text}
    except Exception as e:
        print(f"[!] Erreur transcription endpoint : {e}")
        return {"transcription": "", "error": str(e)}


@app.get("/api/vox/audio/{filename}")
async def get_audio_file(filename: str):
    """Sert un fichier audio MP3 généré par le TTS pour lecture dans l'Orbe."""
    file_path = AUDIO_CACHE_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio non trouvé.")
    return FileResponse(path=str(file_path), media_type="audio/mpeg")


# --- ACTIONS MÉTIER DIRECTES (Validation, Rejet, Résolution) ---

@app.post("/api/drafts/{draft_id}/validate")
async def validate_draft(draft_id: int, modified_body: Optional[str] = Form(None)):
    try:
        draft = repo.validate_draft(draft_id, modified_body=modified_body)
        repo.log_decision(
            type_action="VALIDATION_HUMAINE",
            regles_appliquees=["Validation directe par Akim"],
            resultat="ENVOYE",
            contact_id=draft["contact_id"],
            details=f"Brouillon #{draft_id} validé {'avec modification' if modified_body else 'sans modification'}."
        )
        return RedirectResponse(url="/manual", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/drafts/{draft_id}/reject")
async def reject_draft(draft_id: int, raison: Optional[str] = Form("Rejeté par Akim")):
    try:
        repo.reject_draft(draft_id, raison=raison)
        return RedirectResponse(url="/manual", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, notes: Optional[str] = Form("Résolue")):
    try:
        repo.resolve_alert(alert_id, notes=notes)
        return RedirectResponse(url="/manual", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/simulate-email")
async def simulate_email(
    sender_email: str = Form(...),
    sender_name: str = Form(...),
    subject: str = Form(...),
    content: str = Form(...)
):
    try:
        res = pipeline.process_incoming_email(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            content=content
        )
        return RedirectResponse(url="/manual", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/prospects/generate")
async def run_prospection():
    try:
        prospection_engine.generate_prospects_batch()
        return RedirectResponse(url="/manual", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/briefing/json")
async def get_briefing_json():
    return briefing_synth.generate_briefing()
