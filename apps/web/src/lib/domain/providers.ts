export type MatchStatus = "scheduled" | "finished";

export type Team = {
  id: string;
  name: string;
  shortName: string;
};

export type Match = {
  id: string;
  competition: "Liga MX";
  kickoffAt: string;
  homeTeam: Team;
  awayTeam: Team;
  status: MatchStatus;
};

export type TeamMatchStats = {
  matchId: string;
  teamId: string;
  goals: number;
  shots: number;
  shotsOnTarget: number;
  possession: number;
  corners: number;
};

export type OddsSnapshot = {
  matchId: string;
  market: "over_under_2_5";
  selection: "over" | "under";
  decimalOdds: number;
  capturedAt: string;
  provider: string;
};

export interface SportsDataProvider {
  getUpcomingMatches(): Promise<Match[]>;
  getMatch(matchId: string): Promise<Match | null>;
  getTeamMatchStats(matchId: string): Promise<TeamMatchStats[]>;
}

export interface OddsProvider {
  getOddsSnapshots(matchId: string): Promise<OddsSnapshot[]>;
}
