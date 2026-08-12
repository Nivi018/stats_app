import type {
  Match,
  OddsSnapshot,
  OddsProvider,
  SportsDataProvider,
  Team,
  TeamMatchStats,
} from "../domain/providers";

const TEAMS: Team[] = [
  { id: "mx-ame", name: "Club América", shortName: "AME" },
  { id: "mx-caz", name: "Cruz Azul", shortName: "CAZ" },
  { id: "mx-chi", name: "Chivas", shortName: "CHI" },
  { id: "mx-mon", name: "Monterrey", shortName: "MON" },
  { id: "mx-tig", name: "Tigres UANL", shortName: "TIG" },
  { id: "mx-pum", name: "Pumas UNAM", shortName: "PUM" },
  { id: "mx-tol", name: "Toluca", shortName: "TOL" },
  { id: "mx-pac", name: "Pachuca", shortName: "PAC" },
  { id: "mx-leo", name: "León", shortName: "LEO" },
  { id: "mx-san", name: "Santos Laguna", shortName: "SAN" },
  { id: "mx-atl", name: "Atlas", shortName: "ATL" },
  { id: "mx-nec", name: "Necaxa", shortName: "NEC" },
];

const TEAM_MAP = new Map(TEAMS.map((t) => [t.id, t]));

const HISTORICAL_PAIRS: [string, string][] = [
  ["mx-ame", "mx-chi"],
  ["mx-mon", "mx-san"],
  ["mx-tig", "mx-pum"],
  ["mx-caz", "mx-tol"],
  ["mx-pac", "mx-leo"],
  ["mx-atl", "mx-nec"],
  ["mx-chi", "mx-mon"],
  ["mx-san", "mx-tig"],
  ["mx-pum", "mx-caz"],
  ["mx-tol", "mx-pac"],
  ["mx-leo", "mx-atl"],
  ["mx-nec", "mx-ame"],
  ["mx-ame", "mx-tol"],
  ["mx-mon", "mx-caz"],
  ["mx-tig", "mx-chi"],
  ["mx-pum", "mx-san"],
  ["mx-caz", "mx-atl"],
  ["mx-pac", "mx-nec"],
  ["mx-leo", "mx-tig"],
  ["mx-atl", "mx-pum"],
  ["mx-san", "mx-ame"],
  ["mx-chi", "mx-nec"],
  ["mx-ame", "mx-leo"],
  ["mx-mon", "mx-pac"],
  ["mx-tig", "mx-caz"],
  ["mx-pum", "mx-tol"],
  ["mx-ame", "mx-mon"],
  ["mx-chi", "mx-caz"],
  ["mx-san", "mx-tol"],
  ["mx-tig", "mx-pac"],
];

const UPCOMING_PAIRS: [string, string][] = [
  ["mx-ame", "mx-caz"],
  ["mx-mon", "mx-tig"],
  ["mx-chi", "mx-pum"],
  ["mx-tol", "mx-pac"],
  ["mx-leo", "mx-ame"],
  ["mx-atl", "mx-san"],
  ["mx-nec", "mx-mon"],
  ["mx-caz", "mx-leo"],
  ["mx-tig", "mx-atl"],
  ["mx-pum", "mx-nec"],
  ["mx-san", "mx-chi"],
  ["mx-pac", "mx-tol"],
];

function pickFromSeed(seed: number, options: number[]): number {
  return options[(seed * 7919 + 104729) >>> 0 % options.length];
}

function buildHistoricalMatch(
  home: string,
  away: string,
  index: number,
): { match: Match; stats: TeamMatchStats[] } {
  const seed = index + 1;
  const hg = pickFromSeed(seed, [0, 1, 1, 1, 2, 2, 2, 3]);
  const ag = pickFromSeed(seed + 7, [0, 0, 1, 1, 1, 1, 2, 3]);

  const day = 2 + ((index * 3) % 28);
  const match: Match = {
    id: `match-hist-${String(index + 1).padStart(2, "0")}`,
    competition: "Liga MX",
    kickoffAt: `2026-07-${String(day).padStart(2, "0")}T${index % 2 === 0 ? "19" : "21"}:00:00Z`,
    homeTeam: TEAM_MAP.get(home)!,
    awayTeam: TEAM_MAP.get(away)!,
    status: "finished",
  };

  const stats: TeamMatchStats[] = [
    {
      matchId: match.id,
      teamId: home,
      goals: hg,
      shots: pickFromSeed(seed + 13, [8, 10, 11, 12, 13, 14, 15, 16]),
      shotsOnTarget: pickFromSeed(seed + 19, [3, 4, 5, 5, 6, 6, 7, 8]),
      possession: pickFromSeed(seed + 23, [38, 42, 44, 48, 52, 55, 58, 62]),
      corners: pickFromSeed(seed + 29, [3, 4, 4, 5, 5, 6, 6, 8]),
    },
    {
      matchId: match.id,
      teamId: away,
      goals: ag,
      shots: pickFromSeed(seed + 31, [7, 9, 10, 11, 13, 14, 15, 17]),
      shotsOnTarget: pickFromSeed(seed + 37, [2, 3, 4, 5, 5, 6, 7, 8]),
      possession: 100 - pickFromSeed(seed + 23, [38, 42, 44, 48, 52, 55, 58, 62]),
      corners: pickFromSeed(seed + 41, [2, 3, 4, 4, 5, 6, 7, 7]),
    },
  ];

  return { match, stats };
}

function buildUpcomingMatch(
  home: string,
  away: string,
  index: number,
): Match {
  const day = 3 + ((index * 2) % 28);
  return {
    id: `match-up-${String(index + 1).padStart(2, "0")}`,
    competition: "Liga MX",
    kickoffAt: `2026-08-${String(day).padStart(2, "0")}T${index % 3 === 0 ? "17" : index % 3 === 1 ? "19" : "21"}:00:00Z`,
    homeTeam: TEAM_MAP.get(home)!,
    awayTeam: TEAM_MAP.get(away)!,
    status: "scheduled",
  };
}

function buildOddsSnapshots(
  matchId: string,
  index: number,
): OddsSnapshot[] {
  const seed = index + 1;
  const over = pickFromSeed(seed, [160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 220]) / 100;
  const under = Number(((1 / (1 - (seed * 29 + 17) % 8 / 75)) / 100 * 100).toFixed(2));
  const fairSum = 1 / over + 1 / under;
  const underAdjusted = 1 / (fairSum - 1 / over);

  return [
    {
      matchId,
      market: "over_under_2_5",
      selection: "over",
      decimalOdds: over,
      capturedAt: "2026-08-11T08:00:00Z",
      provider: "demo-odds",
    },
    {
      matchId,
      market: "over_under_2_5",
      selection: "under",
      decimalOdds: Math.round(underAdjusted * 100) / 100,
      capturedAt: "2026-08-11T08:00:00Z",
      provider: "demo-odds",
    },
  ];
}

export const DEMO_MATCHES: Match[] = [];
export const DEMO_STATS: TeamMatchStats[] = [];
export const DEMO_ODDS: OddsSnapshot[] = [];

HISTORICAL_PAIRS.forEach(([h, a], i) => {
  const { match, stats } = buildHistoricalMatch(h, a, i);
  DEMO_MATCHES.push(match);
  DEMO_STATS.push(...stats);
});

UPCOMING_PAIRS.forEach(([h, a], i) => {
  const match = buildUpcomingMatch(h, a, i);
  DEMO_MATCHES.push(match);
  DEMO_ODDS.push(...buildOddsSnapshots(match.id, i));
});

export class DemoSportsDataProvider implements SportsDataProvider {
  getUpcomingMatches(): Promise<Match[]> {
    return Promise.resolve(DEMO_MATCHES.filter((m) => m.status === "scheduled"));
  }

  getMatch(matchId: string): Promise<Match | null> {
    return Promise.resolve(DEMO_MATCHES.find((m) => m.id === matchId) ?? null);
  }

  getTeamMatchStats(matchId: string): Promise<TeamMatchStats[]> {
    return Promise.resolve(DEMO_STATS.filter((s) => s.matchId === matchId));
  }
}

export class DemoOddsProvider implements OddsProvider {
  getOddsSnapshots(matchId: string): Promise<OddsSnapshot[]> {
    return Promise.resolve(DEMO_ODDS.filter((o) => o.matchId === matchId));
  }
}
