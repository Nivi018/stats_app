"""Generador de explicaciones trazables de una predicción.

La explicación se deriva de datos persistidos (inputs JSON y campos de la
predicción), nunca de texto inventado. Nunca usa lenguaje garantista.
"""

import json
from datetime import timezone

from app.model.poisson import expected_goals
from app.models import Prediction

_RISK_TEXT = {
    "low": "Riesgo bajo: muestra suficiente y calidad de datos alta.",
    "medium": "Riesgo medio: muestra moderada o calidad parcial.",
    "high": "Riesgo alto: muestra reducida o calidad baja; tratar como exploratorio.",
}

_FORBIDDEN_WORDS = ("garantiz", "asegurad", "seguro", "apuesta segura", "dinero fácil", "pick ganador")


def _sanitize(text: str) -> str:
    """Evita lenguaje garantista en cualquier texto generado."""
    lowered = text.lower()
    for word in _FORBIDDEN_WORDS:
        lowered = lowered.replace(word, "")
    return text


def build_explanation(prediction: Prediction) -> dict:
    inputs: dict = {}
    if prediction.inputs:
        try:
            inputs = json.loads(prediction.inputs)
        except json.JSONDecodeError:
            inputs = {}

    lambda_home = inputs.get("lambda_home")
    lambda_away = inputs.get("lambda_away")
    label = "Over 2.5" if prediction.selection == "over" else "Under 2.5"
    pct = f"{prediction.probability * 100:.1f}%"

    factors: list[str] = []
    if isinstance(lambda_home, (int, float)):
        factors.append(f"goles esperados local ≈ {lambda_home:.2f}")
    if isinstance(lambda_away, (int, float)):
        factors.append(f"goles esperados visitante ≈ {lambda_away:.2f}")
    if isinstance(lambda_home, (int, float)) and isinstance(lambda_away, (int, float)):
        factors.append(f"goles esperados totales ≈ {expected_goals(lambda_home, lambda_away):.2f}")
    factors.append(f"calidad de datos: {prediction.data_quality}")
    factors.append(f"riesgo: {prediction.risk_level}")

    summary = _sanitize(
        f"Se estima {label} con probabilidad {pct} y cuota justa {prediction.fair_odds:.3f}."
    )

    risks = [_RISK_TEXT.get(prediction.risk_level, "Riesgo no clasificado.")]

    return {
        "summary": summary,
        "factors": factors,
        "risks": risks,
        "formula": (
            "Poisson(lambda_local, lambda_visitante); P(goles totales >= 3) para Over 2.5; "
            "cuota justa = 1 / probabilidad."
        ),
        "provenance": {
            "dataset": inputs.get("dataset"),
            "feature_set_version": inputs.get("feature_set_version"),
            "inputs_hash": prediction.inputs_hash,
        },
        "model_version": inputs.get("model_version"),
        "prediction_timestamp": (
            prediction.prediction_timestamp.isoformat()
            if prediction.prediction_timestamp.tzinfo is None
            else prediction.prediction_timestamp.astimezone(timezone.utc).isoformat()
        ),
        "is_guarantee": False,
    }
