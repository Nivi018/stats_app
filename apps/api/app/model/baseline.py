"""Baseline Poisson versionado: convierte lambdas en una predicción reproducible."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.odds import fair_odds, round_to
from app.model.poisson import over_under_2_5

MODEL_NAME = "poisson"
MODEL_VERSION = "1.0.0"
MARKET = "over_under_2_5"
LAMBDA_MIN = 0.05
LAMBDA_MAX = 5.0


class LambdaOutOfRange(ValueError):
    pass


def clamp_lambda(value: float) -> float:
    if value < LAMBDA_MIN or value > LAMBDA_MAX:
        raise LambdaOutOfRange(f"lambda {value:.3f} fuera de [{LAMBDA_MIN}, {LAMBDA_MAX}]")
    return value


def inputs_hash(lambda_home: float, lambda_away: float, version: str = MODEL_VERSION) -> str:
    payload = json.dumps(
        {"lambda_home": lambda_home, "lambda_away": lambda_away, "version": version},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PoissonPrediction:
    market: str
    selection: str
    probability: float
    fair_odds: float
    model_name: str
    model_version: str
    inputs_hash: str
    lambda_home: float
    lambda_away: float
    predicted_at: datetime

    def as_dict(self) -> dict:
        return {
            "market": self.market,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "inputs_hash": self.inputs_hash,
            "lambda_home": self.lambda_home,
            "lambda_away": self.lambda_away,
        }


class PoissonBaseline:
    """Baseline reproducible: mismos lambdas y versión -> misma salida."""

    MODEL_NAME = MODEL_NAME
    MODEL_VERSION = MODEL_VERSION
    MARKET = MARKET

    def predict(self, lambda_home: float, lambda_away: float) -> tuple[PoissonPrediction, PoissonPrediction]:
        lh = clamp_lambda(lambda_home)
        la = clamp_lambda(lambda_away)
        p_over, p_under = over_under_2_5(lh, la)
        h = inputs_hash(lh, la, self.MODEL_VERSION)
        now = datetime.now(timezone.utc)

        over = PoissonPrediction(
            market=self.MARKET,
            selection="over",
            probability=p_over,
            fair_odds=round_to(fair_odds(p_over), 4),
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            inputs_hash=h,
            lambda_home=lh,
            lambda_away=la,
            predicted_at=now,
        )
        under = PoissonPrediction(
            market=self.MARKET,
            selection="under",
            probability=p_under,
            fair_odds=round_to(fair_odds(p_under), 4),
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            inputs_hash=h,
            lambda_home=lh,
            lambda_away=la,
            predicted_at=now,
        )
        return over, under
