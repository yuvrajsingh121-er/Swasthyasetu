"""SwasthyaSetu prototype backend.

Run with: python app.py
Then open http://127.0.0.1:8000

This is an explainable screening/triage prototype, not a diagnostic device.
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

ROOT = Path(__file__).parent

# Transparent feature weights make the demo reviewable and safer than an
# opaque medical model. These values are placeholders, not clinical rules.
FEATURE_WEIGHTS = {
    "Persistent cough or breathing trouble": 45,
    "Unable to eat or drink normally": 40,
    "I am pregnant or recently gave birth": 32,
    "Fever or feeling hot": 16,
    "Symptoms for more than 3 days": 18,
    "I have diabetes, BP, or heart condition": 20,
    "Child under 5 or adult over 60": 15,
    "Feeling very tired or weak": 10,
    "Stomach pain, vomiting, or loose motions": 10,
    "Headache or body ache": 5,
}


def disease_risk_model(symptoms):
    """Small, explainable prototype classifier.

    It intentionally returns *screening signals*, never a diagnosis. A real
    clinical model would need validated labelled data and clinician review.
    """
    present = set(symptoms)
    signals = []

    def add(label, evidence, base_score):
        matched = [item for item in evidence if item in present]
        if matched:
            confidence = min(90, base_score + (len(matched) - 1) * 12)
            signals.append({
                "label": label,
                "screening_score": confidence,
                "evidence": matched,
                "status": "Needs clinician confirmation",
            })

    add("Respiratory illness risk", ["Persistent cough or breathing trouble", "Fever or feeling hot"], 55)
    add("Gastrointestinal illness / dehydration risk", ["Stomach pain, vomiting, or loose motions", "Unable to eat or drink normally"], 52)
    add("Febrile illness risk", ["Fever or feeling hot", "Headache or body ache", "Feeling very tired or weak"], 38)
    add("Chronic-condition review needed", ["I have diabetes, BP, or heart condition", "Feeling very tired or weak"], 45)
    return sorted(signals, key=lambda signal: signal["screening_score"], reverse=True)[:3]


def triage(payload):
    answers = payload.get("answers", [])
    symptoms = [item for group in answers if isinstance(group, list) for item in group]
    score = min(95, sum(FEATURE_WEIGHTS.get(item, 0) for item in symptoms))
    flags = [item for item in symptoms if item in FEATURE_WEIGHTS]

    result = {"possible_risks": disease_risk_model(symptoms)}
    if score >= 40:
        result.update({
            "priority": "HIGH",
            "score": max(score, 70),
            "title": "Please seek care today.",
            "advice": "Your responses include warning signs. Please visit the listed health centre today or use teleconsultation.",
            "referral_window": "Today",
            "factors": flags[:3],
        })
    elif score >= 15:
        result.update({
            "priority": "MODERATE",
            "score": score,
            "title": "A check-up is recommended.",
            "advice": "Please speak to a healthcare professional within the next 24–48 hours.",
            "referral_window": "Within 24–48 hours",
            "factors": flags[:3],
        })
    else:
        result.update({
            "priority": "LOW",
            "score": score,
            "title": "You can monitor at home.",
            "advice": "No urgent warning signs were identified. If symptoms worsen or persist, please seek medical advice.",
            "referral_window": "Monitor symptoms",
            "factors": flags[:3],
        })
    return result


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/triage":
            self.send_error(404, "Endpoint not found")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 100_000:
                raise ValueError("Request too large")
            payload = json.loads(self.rfile.read(size) or b"{}")
            response = {"disclaimer": "Screening support only — not a diagnosis.", "result": triage(payload)}
            data = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_error(400, str(exc))


if __name__ == "__main__":
    print("SwasthyaSetu backend running at http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler).serve_forever()
