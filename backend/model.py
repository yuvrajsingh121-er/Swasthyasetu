"""Explainable prototype disease-risk model persisted as Pickle.

This model produces screening signals only. It is not clinically validated and
must not be used as a medical diagnosis.
"""
from __future__ import annotations

import pickle
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("models") / "triage_model.pkl"

DEFAULT_MODEL = {
    "weights": {
        "Persistent cough or breathing trouble": 45,
        "Unable to eat or drink normally": 40,
        "I am pregnant or recently gave birth": 32,
        "I have diabetes, BP, or heart condition": 20,
        "Symptoms for more than 3 days": 18,
        "Fever or feeling hot": 16,
        "Child under 5 or adult over 60": 15,
        "Feeling very tired or weak": 10,
        "Stomach pain, vomiting, or loose motions": 10,
        "Headache or body ache": 5,
        "Chest pain or pressure": 90,
        "Rash, body pain, or bleeding": 35,
        "Dizziness or fainting": 30,
    },
    "version": "prototype-1.0",
}


def load_model() -> dict:
    """Load the persisted model; initialise the prototype artifact once."""
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(exist_ok=True)
        with MODEL_PATH.open("wb") as file:
            pickle.dump(DEFAULT_MODEL, file)
    with MODEL_PATH.open("rb") as file:
        return pickle.load(file)


def predict(symptoms: list[str]) -> dict:
    model = load_model()
    present = set(symptoms)
    score = min(95, sum(model["weights"].get(item, 0) for item in present))
    signals = []

    def signal(label: str, evidence: list[str], base: int) -> None:
        matched = [item for item in evidence if item in present]
        if matched:
            signals.append({
                "label": label,
                "score": min(90, base + (len(matched) - 1) * 12),
                "evidence": matched,
                "status": "Needs clinician confirmation",
            })

    signal("Respiratory illness risk", ["Persistent cough or breathing trouble", "Fever or feeling hot"], 55)
    signal("Gastrointestinal illness / dehydration risk", ["Stomach pain, vomiting, or loose motions", "Unable to eat or drink normally"], 52)
    signal("Febrile illness risk", ["Fever or feeling hot", "Headache or body ache", "Feeling very tired or weak"], 38)
    signal("Chronic-condition review needed", ["I have diabetes, BP, or heart condition", "Feeling very tired or weak"], 45)
    signal("Urgent cardiac symptom review", ["Chest pain or pressure", "Dizziness or fainting"], 60)
    signal("Vector-borne illness screening", ["Rash, body pain, or bleeding", "Fever or feeling hot"], 48)

    if score >= 40:
        priority, title, window = "HIGH", "Please seek care today.", "Today"
        advice = "Your responses include warning signs. Please visit a healthcare centre or use teleconsultation today."
    elif score >= 15:
        priority, title, window = "MODERATE", "A check-up is recommended.", "Within 24–48 hours"
        advice = "Please speak to a healthcare professional within the next 24–48 hours."
    else:
        priority, title, window = "LOW", "You can monitor at home.", "Monitor symptoms"
        advice = "No urgent warning signs were identified. Seek medical advice if symptoms worsen or persist."

    return {
        "priority": priority, "score": score, "title": title, "advice": advice,
        "referral_window": window, "possible_risks": sorted(signals, key=lambda item: item["score"], reverse=True)[:3],
        "model_version": model["version"],
    }
