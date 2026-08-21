from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Patient, Screening
from model import predict


# ============================================================
# APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="SwasthyaSetu AI Triage API",
    version="1.0.0"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class TriageRequest(BaseModel):
    patient_id: int | None = None

    symptoms: list[str] = Field(
        default_factory=list,
        max_length=20
    )

    temperature_f: float | None = Field(
        default=None,
        ge=90,
        le=110
    )

    blood_pressure: str | None = Field(
        default=None,
        max_length=12
    )

    blood_sugar: float | None = Field(
        default=None,
        ge=20,
        le=700
    )

    pulse_estimate: int | None = Field(
        default=None,
        ge=35,
        le=220
    )

    spo2: float | None = Field(
        default=None,
        ge=50,
        le=100
    )

    consent: bool = False

    abha_id: str | None = Field(
        default=None,
        max_length=30
    )

# ============================================================
# GET PATIENT HISTORY
# ============================================================

@app.get("/api/v1/patients/{patient_id}")
def get_patient_history(
    patient_id: int,
    db: Session = Depends(get_db)
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if not patient:
        return {
            "success": False,
            "message": "Patient not found"
        }

    screenings = (
        db.query(Screening)
        .filter(Screening.patient_id == patient.id)
        .order_by(Screening.created_at.desc())
        .all()
    )

    return {
        "success": True,

        "patient": {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone": patient.phone,
            "abha_id": patient.abha_id,
            "blood_group": patient.blood_group,
            "chronic_conditions": patient.chronic_conditions,
            "allergies": patient.allergies,
            "pregnancy_or_recent_childbirth": (
                patient.pregnancy_or_recent_childbirth
            ),
            "created_at": patient.created_at,
        },

        "screenings": [
            {
                "id": screening.id,
                "symptoms": screening.symptoms,

                "vitals": {
                    "temperature": screening.temperature,
                    "blood_pressure": screening.blood_pressure,
                    "blood_sugar": screening.blood_sugar,
                    "spo2": screening.spo2,
                    "pulse": screening.pulse,
                },

                "result": {
                    "risk_score": screening.risk_score,
                    "priority": screening.priority,
                    "advice": screening.advice,
                    "referral_window": screening.referral_window,
                    "risk_signals": screening.risk_signals,
                },

                "created_at": screening.created_at,
            }
            for screening in screenings
        ],

        "total_screenings": len(screenings)
    }

class LegacyTriageRequest(BaseModel):
    answers: list[list[str]] = Field(
        default_factory=list,
        max_length=3
    )


class PdfReportRequest(BaseModel):
    profile: dict[str, str | bool] = Field(
        default_factory=dict
    )

    symptoms: list[str] = Field(
        default_factory=list,
        max_length=20
    )

    vitals: dict[str, str | int | float | None] = Field(
        default_factory=dict
    )

    result: dict[str, object]

    nearest_centre: str = Field(
        default="Rampur Community Health Centre",
        max_length=120
    )


class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str | None = None
    phone: str | None = None
    abha_id: str | None = None
    blood_group: str | None = None
    chronic_conditions: str | None = None
    allergies: str | None = None
    pregnancy_or_recent_childbirth: bool = False


# ============================================================
# EMERGENCY SYMPTOMS
# ============================================================

EMERGENCY_SYMPTOMS = {
    "chest pain",
    "chest pain and pressure",
    "difficulty breathing",
    "severe bleeding",
    "unconscious",
    "seizure",
    "stroke",
}


# ============================================================
# HELPER: APPLY EMERGENCY OVERRIDE
# ============================================================

def apply_emergency_override(
    result: dict,
    symptoms: list[str]
) -> dict:
    """
    Override AI result when a potentially emergency symptom
    is explicitly selected.
    """

    symptoms_lower = [
        str(symptom).lower().strip()
        .replace("_", " ")
        for symptom in symptoms
    ]

    detected_emergencies = [
        symptom
        for symptom in symptoms_lower
        if symptom in EMERGENCY_SYMPTOMS
    ]

    if detected_emergencies:

        result["priority"] = "EMERGENCY"

        result["score"] = max(
            int(result.get("score", 0)),
            90
        )

        result["title"] = (
            "Urgent medical evaluation recommended"
        )

        result["advice"] = (
            "Potential emergency warning sign identified. "
            "Seek immediate medical evaluation or emergency care."
        )

        result["referral_window"] = "Immediate"

        # Preserve existing possible risks
        possible_risks = result.get(
            "possible_risks",
            []
        )

        if not isinstance(possible_risks, list):
            possible_risks = []

        # Add emergency signal
        for emergency in detected_emergencies:

            emergency_label = (
                f"Emergency symptom: {emergency}"
            )

            already_exists = any(
                str(item).lower() == emergency_label.lower()
                for item in possible_risks
            )

            if not already_exists:
                possible_risks.append(
                    emergency_label
                )

        result["possible_risks"] = possible_risks

    return result


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "SwasthyaSetu AI Triage API"
    }


# ============================================================
# CREATE PATIENT
# ============================================================

@app.post("/api/v1/patients")
def create_patient(
    request: PatientCreate,
    db: Session = Depends(get_db)
):

    patient = Patient(
        name=request.name,
        age=request.age,
        gender=request.gender,
        phone=request.phone,
        abha_id=request.abha_id,
        blood_group=request.blood_group,
        chronic_conditions=request.chronic_conditions,
        allergies=request.allergies,
        pregnancy_or_recent_childbirth=(
            request.pregnancy_or_recent_childbirth
        ),
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return {
        "success": True,
        "patient_id": patient.id,
        "message": "Patient created successfully"
    }


# ============================================================
# MAIN TRIAGE ENDPOINT
# ============================================================

@app.post("/api/v1/triage")
def triage(
    request: TriageRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # CONSENT CHECK
    # --------------------------------------------------------

    if not request.consent:
        return {
            "success": False,
            "disclaimer": (
                "Consent is required before screening."
            ),
            "result": None
        }

    # --------------------------------------------------------
    # AI / TRIAGE PREDICTION
    # --------------------------------------------------------

    result = predict(request.symptoms)

    # Make sure result is a dictionary
    if not isinstance(result, dict):
        result = {
            "priority": "UNKNOWN",
            "score": 0,
            "title": "Unable to determine risk",
            "advice": (
                "Please seek medical advice for further evaluation."
            ),
            "referral_window": "Clinician review",
            "possible_risks": [],
            "model_version": "prototype-1.0"
        }

    # --------------------------------------------------------
    # EMERGENCY OVERRIDE
    # --------------------------------------------------------

    result = apply_emergency_override(
        result,
        request.symptoms
    )

    # --------------------------------------------------------
    # DEFAULT RESULT FIELDS
    # --------------------------------------------------------

    result.setdefault(
        "priority",
        "UNKNOWN"
    )

    result.setdefault(
        "score",
        0
    )

    result.setdefault(
        "title",
        "Screening completed"
    )

    result.setdefault(
        "advice",
        "Please consult a clinician if symptoms persist."
    )

    result.setdefault(
        "referral_window",
        "Clinician review"
    )

    result.setdefault(
        "possible_risks",
        []
    )

    result.setdefault(
        "model_version",
        "prototype-1.0"
    )

    # --------------------------------------------------------
    # SAVE SCREENING IF PATIENT ID IS PROVIDED
    # --------------------------------------------------------

    if request.patient_id is not None:

        patient = (
            db.query(Patient)
            .filter(
                Patient.id == request.patient_id
            )
            .first()
        )

        # Patient doesn't exist
        if not patient:
            return {
                "success": False,
                "message": "Patient not found"
            }

        # ----------------------------------------------------
        # CREATE SCREENING
        # ----------------------------------------------------

        screening = Screening(

            patient_id=patient.id,

            symptoms=request.symptoms,

            # Vitals
            temperature=request.temperature_f,

            blood_pressure=request.blood_pressure,

            blood_sugar=request.blood_sugar,

            spo2=request.spo2,

            pulse=request.pulse_estimate,

            # AI result
            risk_score=int(
                result.get("score", 0)
            ),

            priority=str(
                result.get(
                    "priority",
                    "UNKNOWN"
                )
            ),

            # IMPORTANT
            # These three fields are saved to DB
            advice=result.get("advice"),

            referral_window=result.get(
                "referral_window"
            ),

            risk_signals=result.get(
                "possible_risks",
                []
            ),
        )

        # ----------------------------------------------------
        # SAVE TO DATABASE
        # ----------------------------------------------------

        db.add(screening)
        db.commit()
        db.refresh(screening)

        # ----------------------------------------------------
        # SUCCESS RESPONSE
        # ----------------------------------------------------

        return {
            "success": True,

            "screening_id": screening.id,

            "patient_id": patient.id,

            "disclaimer": (
                "Screening support only - not a diagnosis. "
                "Clinician confirmation is required."
            ),

            "result": result
        }

    # ========================================================
    # NO PATIENT ID
    # ========================================================

    return {
        "success": True,

        "disclaimer": (
            "Screening support only - not a diagnosis. "
            "Clinician confirmation is required."
        ),

        "result": result
    }


# ============================================================
# LEGACY TRIAGE ENDPOINT
# ============================================================

@app.post("/api/triage")
def legacy_triage(
    request: LegacyTriageRequest
):

    symptoms = [
        item
        for group in request.answers
        for item in group
        if item != "None of these"
    ]

    result = predict(symptoms)

    # Apply emergency override here also
    result = apply_emergency_override(
        result,
        symptoms
    )

    return {
        "disclaimer": (
            "Screening support only - not a diagnosis. "
            "Clinician confirmation is required."
        ),

        "result": result
    }


# ============================================================
# PDF HELPER
# ============================================================

def _pdf_text(value: object) -> str:
    """
    Keep generated PDF text safe for built-in Helvetica font.
    """

    return (
        str(value)
        .encode("latin-1", "replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


# ============================================================
# GENERATE MEDICAL REPORT PDF
# ============================================================

def _medical_report_pdf(
    report: PdfReportRequest
) -> bytes:

    profile = report.profile
    vitals = report.vitals
    result = report.result

    patient = (
        profile.get("name")
        or "Not provided"
    )

    symptoms = (
        ", ".join(report.symptoms)
        if report.symptoms
        else "No symptoms selected"
    )

    risk_rows = (
        result.get("possible_risks")
        if isinstance(
            result.get("possible_risks"),
            list
        )
        else []
    )

    lines = [

        (
            "SwasthyaSetu - Medical Screening Report",
            18
        ),

        (
            "Generated: screening support only - not a diagnosis",
            10
        ),

        ("", 10),

        (
            "PATIENT DETAILS",
            12
        ),

        (
            f"Name: {patient}    "
            f"Age: {profile.get('age') or 'Not provided'}    "
            f"Gender: {profile.get('gender') or 'Not provided'}",
            10
        ),

        (
            f"ABHA ID: {profile.get('abha') or 'Not provided'}    "
            f"Blood group: "
            f"{profile.get('bloodGroup') or 'Not provided'}",
            10
        ),

        (
            f"Existing conditions: "
            f"{profile.get('chronic') or 'None provided'}",
            10
        ),

        (
            f"Allergies: "
            f"{profile.get('allergies') or 'None provided'}",
            10
        ),

        ("", 10),

        (
            "SYMPTOMS AND VITALS",
            12
        ),

        (
            f"Symptoms: {symptoms}",
            10
        ),

        (
            f"Temperature: "
            f"{vitals.get('temperature') or 'Not recorded'} F    "
            f"BP: "
            f"{vitals.get('bp') or 'Not recorded'}",
            10
        ),

        (
            f"Blood sugar: "
            f"{vitals.get('sugar') or 'Not recorded'} mg/dL    "
            f"SpO2: "
            f"{vitals.get('spo2') or 'Not recorded'}%",
            10
        ),

        (
            f"Pulse estimate: "
            f"{vitals.get('pulse') or 'Not recorded'} BPM",
            10
        ),

        ("", 10),

        (
            "SCREENING RESULT",
            12
        ),

        (
            f"Priority: "
            f"{result.get('priority', 'Not available')}    "
            f"Risk score: "
            f"{result.get('score', 'Not available')}",
            10
        ),

        (
            f"Assessment: "
            f"{result.get('title', 'Not available')}",
            10
        ),

        (
            f"Advice: "
            f"{result.get('advice', 'Not available')}",
            10
        ),

        (
            f"Referral: "
            f"{result.get('referral_window', 'Clinician review')} "
            f"at {report.nearest_centre}",
            10
        ),
    ]

    # Add possible risks
    for risk in risk_rows:

        if isinstance(risk, dict):

            lines.append(
                (
                    f"Risk signal: "
                    f"{risk.get('label', '')} "
                    f"({risk.get('score', '')}%)",
                    10
                )
            )

        else:

            lines.append(
                (
                    f"Risk signal: {risk}",
                    10
                )
            )

    # --------------------------------------------------------
    # PDF CONTENT
    # --------------------------------------------------------

    commands = [
        "BT",
        "/F1 10 Tf",
        "50 792 Td"
    ]

    for text, size in lines:

        commands.extend(
            [
                f"/F1 {size} Tf",
                f"({_pdf_text(text)[:130]}) Tj",
                "0 -18 Td"
            ]
        )

    commands.append("ET")

    stream = (
        "\n".join(commands)
        .encode("latin-1", "replace")
    )

    # --------------------------------------------------------
    # PDF OBJECTS
    # --------------------------------------------------------

    objects = [

        b"<< /Type /Catalog /Pages 2 0 R >>",

        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",

        (
            b"<< /Type /Page "
            b"/Parent 2 0 R "
            b"/MediaBox [0 0 595 842] "
            b"/Resources << "
            b"/Font << /F1 5 0 R >> "
            b">> "
            b"/Contents 4 0 R >>"
        ),

        (
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\n"
            b"stream\n"
            + stream
            + b"\nendstream"
        ),

        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    # --------------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------------

    output = bytearray(
        b"%PDF-1.4\n"
    )

    offsets = [0]

    for number, obj in enumerate(
        objects,
        1
    ):

        offsets.append(
            len(output)
        )

        output.extend(
            f"{number} 0 obj\n".encode()
            + obj
            + b"\nendobj\n"
        )

    xref = len(output)

    output.extend(
        (
            f"xref\n"
            f"0 {len(objects) + 1}\n"
            f"0000000000 65535 f \n"
        ).encode()
    )

    output.extend(
        b"".join(
            f"{offset:010d} 00000 n \n".encode()
            for offset in offsets[1:]
        )
    )

    output.extend(
        (
            f"trailer\n"
            f"<< /Size {len(objects) + 1} "
            f"/Root 1 0 R >>\n"
            f"startxref\n"
            f"{xref}\n"
            f"%%EOF"
        ).encode()
    )

    return bytes(output)


# ============================================================
# PDF REPORT ENDPOINT
# ============================================================

@app.post("/api/v1/report.pdf")
def export_pdf_report(
    report: PdfReportRequest
):

    return Response(

        content=_medical_report_pdf(
            report
        ),

        media_type="application/pdf",

        headers={
            "Content-Disposition":
                'attachment; '
                'filename="swasthya-medical-report.pdf"'
        },
    )


# ============================================================
# LEGACY FRONTEND
# ============================================================

@app.get("/legacy")
def legacy_frontend():

    return FileResponse(
        PROJECT_ROOT / "index.html"
    )


# ============================================================
# STATIC FRONTEND
# ============================================================

# Kept LAST so API routes above continue
# to take precedence.
@app.get("/api/v1/patients/{patient_id}/screenings")
def get_patient_screening_history(
    patient_id: int,
    db: Session = Depends(get_db)
):
    # Check whether patient exists
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )

    if not patient:
        return {
            "success": False,
            "message": "Patient not found"
        }

    # Get all screenings for this patient
    screenings = (
        db.query(Screening)
        .filter(Screening.patient_id == patient_id)
        .order_by(Screening.created_at.desc())
        .all()
    )

    screening_history = []

    for screening in screenings:
        screening_history.append({
            "id": screening.id,
            "patient_id": screening.patient_id,
            "symptoms": screening.symptoms,
            "vitals": {
                "temperature": screening.temperature,
                "blood_pressure": screening.blood_pressure,
                "blood_sugar": screening.blood_sugar,
                "spo2": screening.spo2,
                "pulse": screening.pulse,
            },
            "result": {
                "risk_score": screening.risk_score,
                "priority": screening.priority,
                "advice": screening.advice,
                "referral_window": screening.referral_window,
                "risk_signals": screening.risk_signals or [],
            },
            "created_at": screening.created_at,
        })

    return {
        "success": True,
        "patient_id": patient_id,
        "total_screenings": len(screening_history),
        "screenings": screening_history,
    }

@app.get("/api/v1/screenings/{screening_id}")
def get_screening(
    screening_id: int,
    db: Session = Depends(get_db)
):
    screening = (
        db.query(Screening)
        .filter(Screening.id == screening_id)
        .first()
    )

    if not screening:
        return {
            "success": False,
            "message": "Screening not found"
        }

    return {
        "success": True,
        "screening": {
            "id": screening.id,
            "patient_id": screening.patient_id,

            "symptoms": screening.symptoms,

            "vitals": {
                "temperature": screening.temperature,
                "blood_pressure": screening.blood_pressure,
                "blood_sugar": screening.blood_sugar,
                "spo2": screening.spo2,
                "pulse": screening.pulse
            },

            "result": {
                "risk_score": screening.risk_score,
                "priority": screening.priority,
                "advice": screening.advice,
                "referral_window": screening.referral_window,
                "risk_signals": screening.risk_signals or []
            },

            "created_at": screening.created_at
        }
    }
    
app.mount(
    "/",
    StaticFiles(
        directory=str(PROJECT_ROOT),
        html=True
    ),
    name="legacy-assets"
)

