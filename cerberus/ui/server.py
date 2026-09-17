"""
CERBERUS - Serveur Web de Supervision Locale
Module 1 de ZENITH-SYSTEM
"""
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from cerberus.database.repository import Repository
from cerberus.modules.briefing import BriefingSynthesizer
from cerberus.modules.prospection import ProspectionEngine
from cerberus.engine.pipeline import CerberusPipeline
from cerberus.config import CALIBRATION_MODE

app = FastAPI(title="CERBERUS V1 - Supervision", description="Dashboard de supervision pour Akim (ZENITH AI)")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

repo = Repository()
briefing_synth = BriefingSynthesizer(repo)
prospection_engine = ProspectionEngine(repo)
pipeline = CerberusPipeline(repo=repo)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
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



@app.post("/api/drafts/{draft_id}/validate")
async def validate_draft(draft_id: int, modified_body: Optional[str] = Form(None)):
    try:
        draft = repo.validate_draft(draft_id, modified_body=modified_body)
        repo.log_decision(
            type_action="VALIDATION_HUMAINE",
            regles_appliquees="Validation par Akim",
            resultat="ENVOYE",
            contact_id=draft["contact_id"],
            details=f"Brouillon #{draft_id} validé {'avec modification' if modified_body else 'sans modification'}."
        )
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/drafts/{draft_id}/reject")
async def reject_draft(draft_id: int, raison: Optional[str] = Form("Rejeté par Akim")):
    try:
        repo.reject_draft(draft_id, raison=raison)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, notes: Optional[str] = Form("Résolue")):
    try:
        repo.resolve_alert(alert_id, notes=notes)
        return RedirectResponse(url="/", status_code=303)
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
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/prospects/generate")
async def run_prospection():
    try:
        prospection_engine.generate_prospects_batch()
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/briefing/json")
async def get_briefing_json():
    return briefing_synth.generate_briefing()
