"""Dataset demo determinista de Liga MX.

Espeja la lógica de `apps/web/src/lib/data/demo-providers.ts` para que frontend
y backend produzcan exactamente los mismos datos con el mismo seed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

SEED_VERSION = "1.0.0"

TEAMS: list[tuple[str, str, str]] = [
    ("mx-ame", "Club América", "AME"),
    ("mx-caz", "Cruz Azul", "CAZ"),
    ("mx-chi", "Chivas", "CHI"),
    ("mx-mon", "Monterrey", "MON"),
    ("mx-tig", "Tigres UANL", "TIG"),
    ("mx-pum", "Pumas UNAM", "PUM"),
    ("mx-tol", "Toluca", "TOL"),
    ("mx-pac", "Pachuca", "PAC"),
    ("mx-leo", "León", "LEO"),
    ("mx-san", "Santos Laguna", "SAN"),
    ("mx-atl", "Atlas", "ATL"),
    ("mx-nec", "Necaxa", "NEC"),
]

HISTORICAL_PAIRS: list[tuple[str, str]] = [
    ("mx-ame", "mx-chi"),
    ("mx-mon", "mx-san"),
    ("mx-tig", "mx-pum"),
    ("mx-caz", "mx-tol"),
    ("mx-pac", "mx-leo"),
    ("mx-atl", "mx-nec"),
    ("mx-chi", "mx-mon"),
    ("mx-san", "mx-tig"),
    ("mx-pum", "mx-caz"),
    ("mx-tol", "mx-pac"),
    ("mx-leo", "mx-atl"),
    ("mx-nec", "mx-ame"),
    ("mx-ame", "mx-tol"),
    ("mx-mon", "mx-caz"),
    ("mx-tig", "mx-chi"),
    ("mx-pum", "mx-san"),
    ("mx-caz", "mx-atl"),
    ("mx-pac", "mx-nec"),
    ("mx-leo", "mx-tig"),
    ("mx-atl", "mx-pum"),
    ("mx-san", "mx-ame"),
    ("mx-chi", "mx-nec"),
    ("mx-ame", "mx-leo"),
    ("mx-mon", "mx-pac"),
    ("mx-tig", "mx-caz"),
    ("mx-pum", "mx-tol"),
    ("mx-ame", "mx-mon"),
    ("mx-chi", "mx-caz"),
    ("mx-san", "mx-tol"),
    ("mx-tig", "mx-pac"),
]

UPCOMING_PAIRS: list[tuple[str, str]] = [
    ("mx-ame", "mx-caz"),
    ("mx-mon", "mx-tig"),
    ("mx-chi", "mx-pum"),
    ("mx-tol", "mx-pac"),
    ("mx-leo", "mx-ame"),
    ("mx-atl", "mx-san"),
    ("mx-nec", "mx-mon"),
    ("mx-caz", "mx-leo"),
    ("mx-tig", "mx-atl"),
    ("mx-pum", "mx-nec"),
    ("mx-san", "mx-chi"),
    ("mx-pac", "mx-tol"),
]

# Casos intencionales de datos incompletos (identificables por id externo).
# - match-hist-30: partido histórico sin estadísticas (cobertura parcial).
# - match-up-12: partido próximo sin snapshots de cuotas (mercado ausente).
INTENTIONAL_INCOMPLETE_STATS = {"match-hist-30"}
INTENTIONAL_INCOMPLETE_ODDS = {"match-up-12"}


@dataclass
class DemoCompetition:
    external_id: str = "demo-liga-mx"
    name: str = "Liga MX"
    country: str = "México"


@dataclass
class DemoSeason:
    external_id: str = "demo-2026-apertura"
    name: str = "2026 Apertura"
    start_date: datetime = field(
        default_factory=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc)
    )
    end_date: datetime = field(
        default_factory=lambda: datetime(2026, 12, 31, tzinfo=timezone.utc)
    )


@dataclass
class DemoTeam:
    external_id: str
    name: str
    short_name: str


@dataclass
class DemoMatch:
    external_id: str
    season_external_id: str
    home_external_id: str
    away_external_id: str
    kickoff_at: datetime
    status: str
    home_score: int | None
    away_score: int | None


@dataclass
class DemoStats:
    match_external_id: str
    team_external_id: str
    goals: int
    shots: int | None
    shots_on_target: int | None
    possession: float | None
    corners: int | None


@dataclass
class DemoOdds:
    match_external_id: str
    provider: str
    market: str
    line: float
    selection: str
    odds: float
    observed_at: datetime


@dataclass
class DemoDataset:
    version: str
    competition: DemoCompetition
    season: DemoSeason
    teams: list[DemoTeam]
    matches: list[DemoMatch]
    stats: list[DemoStats]
    odds: list[DemoOdds]
    intentional_incomplete: list[str]


def pick_from_seed(seed: int, options: list[int]) -> int:
    return options[(seed * 7919 + 104729) % len(options)]


def _build_historical(home: str, away: str, index: int) -> tuple[DemoMatch, list[DemoStats]]:
    seed = index + 1
    hg = pick_from_seed(seed, [0, 1, 1, 1, 2, 2, 2, 3])
    ag = pick_from_seed(seed + 7, [0, 0, 1, 1, 1, 1, 2, 3])
    day = 2 + ((index * 3) % 28)
    match_id = f"match-hist-{index + 1:02d}"
    kickoff = datetime(2026, 7, day, 19 if index % 2 == 0 else 21, tzinfo=timezone.utc)

    match = DemoMatch(
        external_id=match_id,
        season_external_id="demo-2026-apertura",
        home_external_id=home,
        away_external_id=away,
        kickoff_at=kickoff,
        status="finished",
        home_score=hg,
        away_score=ag,
    )

    if match_id in INTENTIONAL_INCOMPLETE_STATS:
        return match, []

    stats = [
        DemoStats(
            match_external_id=match_id,
            team_external_id=home,
            goals=hg,
            shots=pick_from_seed(seed + 13, [8, 10, 11, 12, 13, 14, 15, 16]),
            shots_on_target=pick_from_seed(seed + 19, [3, 4, 5, 5, 6, 6, 7, 8]),
            possession=pick_from_seed(seed + 23, [38, 42, 44, 48, 52, 55, 58, 62]),
            corners=pick_from_seed(seed + 29, [3, 4, 4, 5, 5, 6, 6, 8]),
        ),
        DemoStats(
            match_external_id=match_id,
            team_external_id=away,
            goals=ag,
            shots=pick_from_seed(seed + 31, [7, 9, 10, 11, 13, 14, 15, 17]),
            shots_on_target=pick_from_seed(seed + 37, [2, 3, 4, 5, 5, 6, 7, 8]),
            possession=100 - pick_from_seed(seed + 23, [38, 42, 44, 48, 52, 55, 58, 62]),
            corners=pick_from_seed(seed + 41, [2, 3, 4, 4, 5, 6, 7, 7]),
        ),
    ]
    return match, stats


def _build_upcoming(home: str, away: str, index: int) -> DemoMatch:
    day = 3 + ((index * 2) % 28)
    hour = [17, 19, 21][index % 3]
    return DemoMatch(
        external_id=f"match-up-{index + 1:02d}",
        season_external_id="demo-2026-apertura",
        home_external_id=home,
        away_external_id=away,
        kickoff_at=datetime(2026, 8, day, hour, tzinfo=timezone.utc),
        status="scheduled",
        home_score=None,
        away_score=None,
    )


def _build_odds(match_id: str, index: int) -> list[DemoOdds]:
    if match_id in INTENTIONAL_INCOMPLETE_ODDS:
        return []

    seed = index + 1
    over = pick_from_seed(seed, [160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 220]) / 100
    under_base = 1 / (1 - (seed * 29 + 17) % 8 / 75)
    fair_sum = 1 / over + 1 / under_base
    under = round(1 / (fair_sum - 1 / over), 2)
    observed = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)

    return [
        DemoOdds(
            match_external_id=match_id,
            provider="demo-odds",
            market="over_under_2_5",
            line=2.5,
            selection="over",
            odds=over,
            observed_at=observed,
        ),
        DemoOdds(
            match_external_id=match_id,
            provider="demo-odds",
            market="over_under_2_5",
            line=2.5,
            selection="under",
            odds=under,
            observed_at=observed,
        ),
    ]


def build_demo_dataset() -> DemoDataset:
    teams = [DemoTeam(external_id=eid, name=name, short_name=short) for eid, name, short in TEAMS]
    matches: list[DemoMatch] = []
    stats: list[DemoStats] = []
    odds: list[DemoOdds] = []

    for i, (home, away) in enumerate(HISTORICAL_PAIRS):
        match, match_stats = _build_historical(home, away, i)
        matches.append(match)
        stats.extend(match_stats)

    for i, (home, away) in enumerate(UPCOMING_PAIRS):
        match = _build_upcoming(home, away, i)
        matches.append(match)
        odds.extend(_build_odds(match.external_id, i))

    intentional = sorted(INTENTIONAL_INCOMPLETE_STATS | INTENTIONAL_INCOMPLETE_ODDS)
    return DemoDataset(
        version=SEED_VERSION,
        competition=DemoCompetition(),
        season=DemoSeason(),
        teams=teams,
        matches=matches,
        stats=stats,
        odds=odds,
        intentional_incomplete=intentional,
    )


def dataset_counts(dataset: DemoDataset) -> dict[str, int]:
    return {
        "teams": len(dataset.teams),
        "matches_historical": sum(1 for m in dataset.matches if m.status == "finished"),
        "matches_upcoming": sum(1 for m in dataset.matches if m.status == "scheduled"),
        "stats": len(dataset.stats),
        "odds": len(dataset.odds),
    }
