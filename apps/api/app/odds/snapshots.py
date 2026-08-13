"""Selección y validación de snapshots de cuotas según la política.

Implementa el documento normativo "10 | Política de snapshots de cuotas y CLV":
- Identidad y tres timestamps (observed/received/ingested).
- Elegibilidad por prediction_timestamp y frescura.
- Opening/closing reproducibles.
- De-vig con pares comparables (over+under dentro de `MAX_PAIR_GAP`).
- Consenso por mediana con >=3 fuentes y overround sano.
- Correcciones sin sobrescribir (correction_of_id).
- Detección de cuota inválida, mercado inválido, duplicado, fuera de orden,
  suspensión y overround anómalo.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from app.domain.market import (
    LINE_2_5,
    MAX_PAIR_GAP,
    MAX_SNAPSHOT_AGE,
    MARKET_OVER_UNDER,
    OVERROUND_MAX,
    OVERROUND_MIN,
    VALID_SELECTIONS,
    InvalidMarketError,
    InvalidOddsError,
    overround,
    overround_is_anomalous,
    remove_margin,
    validate_odds,
)

OPEN = "open"
SUSPENDED = "suspended"
CLOSED = "closed"
VALID_STATUSES = frozenset({OPEN, SUSPENDED, CLOSED})


@dataclass(frozen=True)
class Snapshot:
    id: str
    match_id: str
    provider: str
    market: str
    line: float
    selection: str
    odds: float
    observed_at: datetime
    received_at: datetime
    market_status: str
    correction_of_id: str | None = None
    idempotency_key: str | None = None

    @classmethod
    def from_model(cls, model) -> "Snapshot":
        observed = model.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        received = model.received_at
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        return cls(
            id=str(model.id),
            match_id=str(model.match_id),
            provider=model.provider,
            market=model.market,
            line=model.line,
            selection=model.selection,
            odds=model.odds,
            observed_at=observed,
            received_at=received,
            market_status=model.market_status,
            correction_of_id=str(model.correction_of_id) if model.correction_of_id else None,
            idempotency_key=model.idempotency_key,
        )


@dataclass(frozen=True)
class SnapshotIssue:
    severity: str  # critical | warning | info
    kind: str
    message: str
    snapshot_id: str


@dataclass(frozen=True)
class Pair:
    over: Snapshot
    under: Snapshot

    @property
    def no_vig_probabilities(self) -> tuple[float, float]:
        return remove_margin(self.over.odds, self.under.odds)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def is_valid_snapshot(snapshot: Snapshot) -> bool:
    try:
        validate_odds(snapshot.odds)
    except InvalidOddsError:
        return False
    return (
        snapshot.market == MARKET_OVER_UNDER
        and snapshot.line == LINE_2_5
        and snapshot.selection in VALID_SELECTIONS
        and snapshot.market_status in VALID_STATUSES
    )


def is_eligible_at(
    snapshot: Snapshot,
    prediction_timestamp: datetime,
    kickoff_at: datetime | None = None,
    max_age_seconds: float = MAX_SNAPSHOT_AGE,
) -> bool:
    if not is_valid_snapshot(snapshot):
        return False
    if snapshot.market_status != OPEN:
        return False
    observed = _as_utc(snapshot.observed_at)
    at = _as_utc(prediction_timestamp)
    if observed > at:
        return False
    if at - observed > timedelta(seconds=max_age_seconds):
        return False
    if kickoff_at is not None and observed >= _as_utc(kickoff_at):
        return False
    return True


def opening(snapshots: list[Snapshot], kickoff_at: datetime | None = None) -> Snapshot | None:
    valid = [s for s in snapshots if is_valid_snapshot(s)]
    if kickoff_at is not None:
        kickoff = _as_utc(kickoff_at)
        valid = [s for s in valid if _as_utc(s.observed_at) < kickoff]
    if not valid:
        return None
    return min(valid, key=lambda s: _as_utc(s.observed_at))


def closing(snapshots: list[Snapshot], kickoff_at: datetime | None = None) -> Snapshot | None:
    valid = [s for s in snapshots if is_valid_snapshot(s) and s.market_status == OPEN]
    if kickoff_at is not None:
        kickoff = _as_utc(kickoff_at)
        valid = [s for s in valid if _as_utc(s.observed_at) < kickoff]
    if not valid:
        return None
    return max(valid, key=lambda s: _as_utc(s.observed_at))


def de_vig_pair(
    snapshots: list[Snapshot],
    at: datetime,
    max_gap_seconds: float = MAX_PAIR_GAP,
) -> Pair | None:
    at_utc = _as_utc(at)
    eligible = [s for s in snapshots if is_eligible_at(s, at_utc)]
    over = [s for s in eligible if s.selection == "over"]
    under = [s for s in eligible if s.selection == "under"]
    for o in over:
        for u in under:
            gap = abs((_as_utc(o.observed_at) - _as_utc(u.observed_at)).total_seconds())
            if gap <= max_gap_seconds:
                return Pair(over=o, under=u)
    return None


def consensus_probability(
    snapshots: list[Snapshot],
    at: datetime,
    selection: str,
    min_sources: int = 3,
) -> float | None:
    """Mediana de probabilidad sin margen para `selection` con >=3 fuentes."""
    at_utc = _as_utc(at)
    by_provider: dict[str, float] = {}
    for snap in snapshots:
        if not is_eligible_at(snap, at_utc):
            continue
        pair = _find_pair_for(snap, snapshots, at_utc)
        if pair is None:
            continue
        p_over, p_under = pair.no_vig_probabilities
        by_provider[snap.provider] = p_over if selection == "over" else p_under
    if len(by_provider) < min_sources:
        return None
    return median(by_provider.values())


def _find_pair_for(snap: Snapshot, snapshots: list[Snapshot], at: datetime) -> Pair | None:
    candidates = [s for s in snapshots if s.selection != snap.selection and is_eligible_at(s, at)]
    if not candidates:
        return None
    same_provider = [s for s in candidates if s.provider == snap.provider]
    pool = same_provider or candidates
    other = min(pool, key=lambda s: abs((_as_utc(s.observed_at) - _as_utc(snap.observed_at)).total_seconds()))
    gap = abs((_as_utc(other.observed_at) - _as_utc(snap.observed_at)).total_seconds())
    if gap > MAX_PAIR_GAP:
        return None
    if snap.selection == "over":
        return Pair(over=snap, under=other)
    return Pair(over=other, under=snap)


def validate_snapshots(snapshots: list[Snapshot]) -> list[SnapshotIssue]:
    """Detecta cuotas/mercado inválidos, duplicados, fuera de orden, suspensión y overround anómalo."""
    issues: list[SnapshotIssue] = []
    seen: set[tuple] = set()

    for s in snapshots:
        try:
            validate_odds(s.odds)
        except InvalidOddsError as exc:
            issues.append(SnapshotIssue("critical", "invalid_odds", str(exc), s.id))
            continue

        if s.market != MARKET_OVER_UNDER or s.line != LINE_2_5 or s.selection not in VALID_SELECTIONS:
            issues.append(
                SnapshotIssue("critical", "invalid_market", f"Mercado/línea/selección fuera de contrato: {s.market}/{s.line}/{s.selection}", s.id)
            )
            continue

        key = (s.provider, s.market, s.selection, _as_utc(s.observed_at))
        if key in seen:
            issues.append(SnapshotIssue("warning", "duplicate", "Snapshot duplicado (misma fuente/mercado/selección/timestamp)", s.id))
        seen.add(key)

        observed = _as_utc(s.observed_at)
        received = _as_utc(s.received_at)
        if observed > datetime.now(timezone.utc):
            issues.append(SnapshotIssue("warning", "future_timestamp", "observed_at en el futuro", s.id))
        if received < observed:
            issues.append(SnapshotIssue("warning", "out_of_order", "received_at anterior a observed_at", s.id))
        if s.market_status == SUSPENDED:
            issues.append(SnapshotIssue("info", "suspended", "Mercado suspendido: excluido del precio elegible", s.id))

    # Overround anómalo por par comparable por proveedor.
    by_pair: dict[tuple[str, datetime], list[Snapshot]] = {}
    for s in snapshots:
        if s.selection not in VALID_SELECTIONS or s.market_status != OPEN:
            continue
        by_pair.setdefault((s.provider, _as_utc(s.observed_at)), []).append(s)
    for (_provider, _at), pair_snapshots in by_pair.items():
        selections = {p.selection for p in pair_snapshots}
        if selections == {"over", "under"}:
            over = next(p for p in pair_snapshots if p.selection == "over")
            under = next(p for p in pair_snapshots if p.selection == "under")
            value = overround(over.odds, under.odds)
            if not (OVERROUND_MIN <= value <= OVERROUND_MAX):
                issues.append(
                    SnapshotIssue("warning", "overround_anomaly", f"Overround {value:.3f} fuera de [{OVERROUND_MIN}, {OVERROUND_MAX}]", over.id)
                )
    return issues


def overround_for(snapshots: list[Snapshot], at: datetime) -> float | None:
    pair = de_vig_pair(snapshots, at)
    if pair is None:
        return None
    return overround(pair.over.odds, pair.under.odds)
