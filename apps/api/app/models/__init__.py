import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    seasons: Mapped[list["Season"]] = relationship(back_populates="competition")


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competitions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    competition: Mapped["Competition"] = relationship(back_populates="seasons")
    matches: Mapped[list["Match"]] = relationship(back_populates="season")

    __table_args__ = (
        UniqueConstraint("competition_id", "name", name="uq_season_competition_name"),
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    home_matches: Mapped[list["Match"]] = relationship(foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches: Mapped[list["Match"]] = relationship(foreign_keys="Match.away_team_id", back_populates="away_team")
    stats: Mapped[list["TeamMatchStats"]] = relationship(back_populates="team")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id"), nullable=False, index=True)
    home_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column(nullable=True)
    away_score: Mapped[int | None] = mapped_column(nullable=True)
    matchday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_demo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    season: Mapped["Season"] = relationship(back_populates="matches")
    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id], back_populates="home_matches")
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id], back_populates="away_matches")
    stats: Mapped[list["TeamMatchStats"]] = relationship(back_populates="match")
    odds_snapshots: Mapped[list["OddsSnapshot"]] = relationship(back_populates="match")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match")


class TeamMatchStats(Base):
    __tablename__ = "team_match_stats"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    goals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    possession: Mapped[float | None] = mapped_column(Float, nullable=True)
    corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fouls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_demo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["Match"] = relationship(back_populates="stats")
    team: Mapped["Team"] = relationship(back_populates="stats")

    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_stats_match_team"),
    )


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    line: Mapped[float] = mapped_column(Float, nullable=False)
    selection: Mapped[str] = mapped_column(String(16), nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("odds_snapshots.id"), nullable=True)
    market_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    is_demo: Mapped[bool] = mapped_column(default=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["Match"] = relationship(back_populates="odds_snapshots")
    correction_of: Mapped["OddsSnapshot | None"] = relationship(remote_side=[id])

    __table_args__ = (
        UniqueConstraint("match_id", "provider", "market", "selection", "observed_at", name="uq_odds_snapshot"),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    feature_set_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[str] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="model_version")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_version"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    selection: Mapped[str] = mapped_column(String(16), nullable=False)
    line: Mapped[float | None] = mapped_column(Float, nullable=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    fair_odds: Mapped[float] = mapped_column(Float, nullable=False)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    no_vig_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_quality: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["Match"] = relationship(back_populates="predictions")
    model_version: Mapped["ModelVersion"] = relationship(back_populates="predictions")
    outcomes: Mapped[list["PredictionOutcome"]] = relationship(back_populates="prediction")


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("predictions.id"), nullable=False, unique=True, index=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prediction: Mapped["Prediction"] = relationship(back_populates="outcomes")


class Parlay(Base):
    __tablename__ = "parlays"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    selections: Mapped[str] = mapped_column(Text, nullable=False)
    combined_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=True)
    correlation_warning: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
