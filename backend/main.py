from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from model import predict

app = FastAPI(title="SwasthyaSetu AI Triage API", version="1.0.0")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


class TriageRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    temperature_f: float | None = Field(default=None, ge=90, le=110)
    blood_pressure: str | None = Field(default=None, max_length=12)
    blood_sugar: float | None = Field(default=None, ge=20, le=700)
    pulse_estimate: int | None = Field(default=None, ge=35, le=220)
    spo2: float | None = Field(default=None, ge=50, le=100)
    consent: bool = False
    abha_id: str | None = Field(default=None, max_length=30)


class LegacyTriageRequest(BaseModel):
    answers: list[list[str]] = Field(default_factory=list, max_length=3)


class PdfReportRequest(BaseModel):
    profile: dict[str, str | bool] = Field(default_factory=dict)
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    vitals: dict[str, str | int | float | None] = Field(default_factory=dict)
    result: dict[str, object]
    nearest_centre: str = Field(default="Rampur Community Health Centre", max_length=120)


def _pdf_text(value: object) -> str:
    """Keep generated PDF text safe for the built-in Helvetica font."""
    return str(value).encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _medical_report_pdf(report: PdfReportRequest) -> bytes:
    """Create a small self-contained PDF without storing patient data on disk."""
    profile, vitals, result = report.profile, report.vitals, report.result
    patient = profile.get("name") or "Not provided"
    symptoms = ", ".join(report.symptoms) if report.symptoms else "No symptoms selected"
    risk_rows = result.get("possible_risks") if isinstance(result.get("possible_risks"), list) else []
    lines = [
        ("SwasthyaSetu - Medical Screening Report", 18),
        ("Generated: screening support only - not a diagnosis", 10),
        ("", 10),
        ("PATIENT DETAILS", 12),
        (f"Name: {patient}    Age: {profile.get('age') or 'Not provided'}    Gender: {profile.get('gender') or 'Not provided'}", 10),
        (f"ABHA ID: {profile.get('abha') or 'Not provided'}    Blood group: {profile.get('bloodGroup') or 'Not provided'}", 10),
        (f"Existing conditions: {profile.get('chronic') or 'None provided'}", 10),
        (f"Allergies: {profile.get('allergies') or 'None provided'}", 10),
        ("", 10),
        ("SYMPTOMS AND VITALS", 12),
        (f"Symptoms: {symptoms}", 10),
        (f"Temperature: {vitals.get('temperature') or 'Not recorded'} F    BP: {vitals.get('bp') or 'Not recorded'}", 10),
        (f"Blood sugar: {vitals.get('sugar') or 'Not recorded'} mg/dL    SpO2: {vitals.get('spo2') or 'Not recorded'}%", 10),
        (f"Pulse estimate: {vitals.get('pulse') or 'Not recorded'} BPM", 10),
        ("", 10),
        ("SCREENING RESULT", 12),
        (f"Priority: {result.get('priority', 'Not available')}    Risk score: {result.get('score', 'Not available')}", 10),
        (f"Assessment: {result.get('title', 'Not available')}", 10),
        (f"Advice: {result.get('advice', 'Not available')}", 10),
        (f"Referral: {result.get('referral_window', 'Clinician review')} at {report.nearest_centre}", 10),
    ]
    for risk in risk_rows:
        if isinstance(risk, dict):
            lines.append((f"Risk signal: {risk.get('label', '')} ({risk.get('score', '')}%)", 10))

    # A single-page, standard PDF with one text stream. Long values are truncated
    # so the report stays legible rather than overflowing its page.
    commands = ["BT", "/F1 10 Tf", "50 792 Td"]
    for text, size in lines:
        commands.extend([f"/F1 {size} Tf", f"({_pdf_text(text)[:130]}) Tj", "0 -18 Td"])
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


@app.get("/health")
def health():
    return {"status": "ok", "service": "SwasthyaSetu AI Triage API"}


@app.post("/api/v1/triage")
def triage(request: TriageRequest):
    if not request.consent:
        return {"disclaimer": "Consent is required before screening.", "result": None}
    result = predict(request.symptoms)
    return {
        "disclaimer": "Screening support only — not a diagnosis. Clinician confirmation is required.",
        "result": result,
    }


@app.post("/api/triage")
def legacy_triage(request: LegacyTriageRequest):
    """Compatibility endpoint for the root HTML prototype."""
    symptoms = [item for group in request.answers for item in group if item != "None of these"]
    return {
        "disclaimer": "Screening support only — not a diagnosis. Clinician confirmation is required.",
        "result": predict(symptoms),
    }


@app.post("/api/v1/report.pdf")
def export_pdf_report(report: PdfReportRequest):
    return Response(
        content=_medical_report_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="swasthya-medical-report.pdf"'},
    )


@app.get("/legacy")
def legacy_frontend():
    return FileResponse(PROJECT_ROOT / "index.html")


# Kept last so API routes above continue to take precedence.
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT), html=True), name="legacy-assets")
