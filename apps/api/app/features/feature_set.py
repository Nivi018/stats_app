"""FeatureSet v1 conforme al diccionario de features y dataset de modelado.

Ventanas 10/5, half-life 5, separación local/visita, arrastre de temporada
(0.75), fallbacks, muestras mínimas y clamps. Solo usa partidos finalizados
anteriores a `prediction_timestamp`; excluye cuotas y datos futuros.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competition, Match, Season, Team

FEATURE_SET_VERSION = "1.0.0"

WINDOW_TOTAL = 10
WINDOW_CONTEXT = 5
HALF_LIFE = 5.0
SEASON_CARRYOVER_WEIGHT = 0.75
FORM_CLAMP = (0.85, 1.15)
LAMBDA_CLAMP = (0.05, 5.0)

QUALITY_HIGH_TOTAL = 10
QUALITY_HIGH_CONTEXT = 5
QUALITY_MEDIUM_TOTAL = 6
QUALITY_MEDIUM_CONTEXT = 3
MIN_TOTAL_FOR_PREDICTION = 3

LEAGUE_PRIOR = 1.3  # prior de liga para equipos nuevos/ascendidos


@dataclass(frozen=True)
class FeatureVector:
    version: str
    feature_set_hash: str
    match_id: str
    goals_for_weighted: float
    goals_against_weighted: float
    home_goals_for: float
    home_goals_against: float
    away_goals_for: float
    away_goals_against: float
    recent_form_goals_delta: float
    league_home_goal_rate: float
    league_away_goal_rate: float
    sample_size_total: int
    sample_size_context: int
    lambda_home: float
    lambda_away: float
    data_quality: str
    risk_level: str
    fallbacks: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _Row:
    kickoff: datetime
    goals_for: float
    goals_against: float
    is_home: bool
    current_season: bool


class FeatureSet:
    VERSION = FEATURE_SET_VERSION

    @staticmethod
    def feature_set_hash() -> str:
        payload = {
            "version": FEATURE_SET_VERSION,
            "window_total": WINDOW_TOTAL,
            "window_context": WINDOW_CONTEXT,
            "half_life": HALF_LIFE,
            "carryover_weight": SEASON_CARRYOVER_WEIGHT,
            "form_clamp": list(FORM_CLAMP),
            "lambda_clamp": list(LAMBDA_CLAMP),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    async def compute(
        self,
        session: AsyncSession,
        match_external_id: str,
        prediction_timestamp: datetime,
    ) -> FeatureVector | None:
        ts = prediction_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        match = (
            await session.execute(select(Match).where(Match.external_id == match_external_id))
        ).scalar_one_or_none()
        if match is None:
            return None

        season = (
            await session.execute(select(Season).where(Season.id == match.season_id))
        ).scalar_one()
        competition = (
            await session.execute(select(Competition).where(Competition.id == season.competition_id))
        ).scalar_one()

        previous_season = await self._previous_season(session, competition.id, season.start_date)

        home_rows = await self._team_rows(session, match.home_team_id, competition.id, season.id, previous_season, ts)
        away_rows = await self._team_rows(session, match.away_team_id, competition.id, season.id, previous_season, ts)

        sample_total = max(len(home_rows), len(away_rows))
        if sample_total < MIN_TOTAL_FOR_PREDICTION:
            return None

        league_home_rate, league_away_rate = await self._league_rates(session, season.id, ts)

        home_features, home_fallbacks = self._features_for(home_rows, is_context_home=True)
        away_features, away_fallbacks = self._features_for(away_rows, is_context_home=False)

        fallbacks = tuple(sorted(set(home_fallbacks) | set(away_fallbacks)))

        lambda_home = self._lambda(
            home_features["goals_for"],
            home_features["goals_against"],
            home_features["context_goals_for"],
            home_features["context_goals_against"],
            league_home_rate,
            league_away_rate,
            home_features["form_delta"],
            is_home=True,
        )
        lambda_away = self._lambda(
            away_features["goals_for"],
            away_features["goals_against"],
            away_features["context_goals_for"],
            away_features["context_goals_against"],
            league_away_rate,
            league_home_rate,
            away_features["form_delta"],
            is_home=False,
        )

        context_size = max(home_features["context_size"], away_features["context_size"])
        quality, risk = self._levels(sample_total, context_size, fallbacks)

        return FeatureVector(
            version=self.VERSION,
            feature_set_hash=self.feature_set_hash(),
            match_id=match_external_id,
            goals_for_weighted=home_features["goals_for"],
            goals_against_weighted=home_features["goals_against"],
            home_goals_for=home_features["context_goals_for"],
            home_goals_against=home_features["context_goals_against"],
            away_goals_for=away_features["context_goals_for"],
            away_goals_against=away_features["context_goals_against"],
            recent_form_goals_delta=max(home_features["form_delta"], away_features["form_delta"]),
            league_home_goal_rate=league_home_rate,
            league_away_goal_rate=league_away_rate,
            sample_size_total=sample_total,
            sample_size_context=context_size,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            data_quality=quality,
            risk_level=risk,
            fallbacks=fallbacks,
        )

    async def _previous_season(self, session, competition_id, current_start) -> Season | None:
        result = await session.execute(
            select(Season)
            .where(Season.competition_id == competition_id, Season.start_date < current_start)
            .order_by(Season.start_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _team_rows(
        self,
        session,
        team_id,
        competition_id,
        current_season_id,
        previous_season,
        ts,
    ) -> list[_Row]:
        result = await session.execute(
            select(Match, Season.id)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .where(
                Competition.id == competition_id,
                Match.status == "finished",
                Match.kickoff_at < ts,
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            )
            .order_by(Match.kickoff_at)
        )
        rows: list[_Row] = []
        for match, season_id in result.all():
            if match.home_team_id == team_id:
                gf, ga, is_home = match.home_score or 0, match.away_score or 0, True
            else:
                gf, ga, is_home = match.away_score or 0, match.home_score or 0, False
            rows.append(
                _Row(
                    kickoff=match.kickoff_at,
                    goals_for=gf,
                    goals_against=ga,
                    is_home=is_home,
                    current_season=(season_id == current_season_id),
                )
            )
        # Arrastre de temporada anterior: se agregan con factor 0.75.
        if previous_season is not None and len(rows) < WINDOW_TOTAL:
            result = await session.execute(
                select(Match)
                .where(
                    Match.season_id == previous_season.id,
                    Match.status == "finished",
                    Match.kickoff_at < ts,
                    (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
                )
                .order_by(Match.kickoff_at)
            )
            for match in result.scalars().all():
                if match.home_team_id == team_id:
                    gf, ga, is_home = match.home_score or 0, match.away_score or 0, True
                else:
                    gf, ga, is_home = match.away_score or 0, match.home_score or 0, False
                rows.append(
                    _Row(
                        kickoff=match.kickoff_at,
                        goals_for=gf,
                        goals_against=ga,
                        is_home=is_home,
                        current_season=False,
                    )
                )
        return rows

    async def _league_rates(self, session, season_id, ts) -> tuple[float, float]:
        result = await session.execute(
            select(Match).where(Match.season_id == season_id, Match.status == "finished", Match.kickoff_at < ts)
        )
        matches = result.scalars().all()
        if not matches:
            return LEAGUE_PRIOR, LEAGUE_PRIOR
        home_goals = [m.home_score or 0 for m in matches]
        away_goals = [m.away_score or 0 for m in matches]
        return sum(home_goals) / len(matches), sum(away_goals) / len(matches)

    def _features_for(self, rows: list[_Row], is_context_home: bool) -> tuple[dict, list[str]]:
        fallbacks: list[str] = []
        newest_first = sorted(rows, key=lambda r: r.kickoff, reverse=True)[:WINDOW_TOTAL]
        gf = self._weighted([r.goals_for for r in newest_first], [self._carry(r) for r in newest_first])
        ga = self._weighted([r.goals_against for r in newest_first], [self._carry(r) for r in newest_first])

        context_rows = [r for r in newest_first if r.is_home == is_context_home][:WINDOW_CONTEXT]
        context_used = len(context_rows) >= 1
        if not context_used:
            context_rows = newest_first[:WINDOW_CONTEXT]
            fallbacks.append("contexto local/visita insuficiente; se usó promedio total")

        cgf = self._weighted([r.goals_for for r in context_rows], [self._carry(r) for r in context_rows]) if context_rows else gf
        cga = self._weighted([r.goals_against for r in context_rows], [self._carry(r) for r in context_rows]) if context_rows else ga

        recent = newest_first[:WINDOW_CONTEXT]
        form_delta = self._weighted(
            [(r.goals_for - r.goals_against) for r in recent],
            [self._carry(r) for r in recent],
        ) if recent else 0.0

        return {
            "goals_for": gf,
            "goals_against": ga,
            "context_goals_for": cgf,
            "context_goals_against": cga,
            "form_delta": form_delta,
            "context_size": len([r for r in newest_first if r.is_home == is_context_home]),
        }, fallbacks

    @staticmethod
    def _carry(row: _Row) -> float:
        return SEASON_CARRYOVER_WEIGHT if not row.current_season else 1.0

    @staticmethod
    def _weighted(values: list[float], weights: list[float]) -> float:
        total_w = sum(weights)
        if total_w == 0:
            return 0.0
        # Decaimiento por recencia: posición 0 es la más reciente.
        decayed = sum(w * 0.5 ** (i / HALF_LIFE) for i, (w, v) in enumerate(zip(weights, values)))
        decayed_w = sum(w * 0.5 ** (i / HALF_LIFE) for i, w in enumerate(weights))
        return decayed / decayed_w if decayed_w else 0.0

    def _lambda(
        self,
        gf, ga, cgf, cga,
        league_rate_own, league_rate_opp,
        form_delta,
        is_home: bool,
    ) -> float:
        attack = (cgf / league_rate_own) if league_rate_own else 1.0
        defense = (cga / league_rate_opp) if league_rate_opp else 1.0
        base = league_rate_own * attack * defense
        adjustment = 1.0 + (form_delta / 10.0)
        adjustment = min(FORM_CLAMP[1], max(FORM_CLAMP[0], adjustment))
        lam = base * adjustment
        if is_home:
            lam *= 1.05  # ligera ventaja de local
        return min(LAMBDA_CLAMP[1], max(LAMBDA_CLAMP[0], lam))

    @staticmethod
    def _levels(sample_total: int, context_size: int, fallbacks) -> tuple[str, str]:
        if fallbacks:
            quality = "low"
        elif sample_total >= QUALITY_HIGH_TOTAL and context_size >= QUALITY_HIGH_CONTEXT:
            quality = "high"
        elif sample_total >= QUALITY_MEDIUM_TOTAL and context_size >= QUALITY_MEDIUM_CONTEXT:
            quality = "medium"
        else:
            quality = "low"

        if sample_total >= QUALITY_HIGH_TOTAL:
            risk = "low"
        elif sample_total >= QUALITY_MEDIUM_TOTAL:
            risk = "medium"
        else:
            risk = "high"
        return quality, risk
