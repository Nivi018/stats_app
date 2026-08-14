// Cliente tipado del API v1. Espeja el OpenAPI canónico en packages/contracts.

export type Team = {
  id: string;
  name: string;
  short_name: string;
};

export type MatchDto = {
  id: string;
  competition: string;
  kickoff_at: string;
  home_team: Team;
  away_team: Team;
  status: "scheduled" | "finished";
  over_odds: number | null;
  under_odds: number | null;
};

export type MatchdayDto = {
  matchday: number;
  updated_at: string;
  total_matches: number;
  matches: MatchDto[];
};

export type ErrorDto = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  correlation_id: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public payload: ErrorDto,
  ) {
    super(payload.message);
    this.name = "ApiError";
  }
}

export async function fetchMatchday(): Promise<MatchdayDto> {
  const response = await fetch("/api/v1/matchdays/current", {
    next: { revalidate: 60 },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }

  return (await response.json()) as MatchdayDto;
}

export type OpportunityDto = {
  match_id: string;
  home_team_short: string;
  away_team_short: string;
  kickoff_at: string;
  market: string;
  selection: "over" | "under";
  model_probability: number;
  market_no_vig_probability: number;
  observed_odds: number;
  fair_odds: number;
  edge_pp: number;
  ev: number;
  data_quality: string;
  risk_level: string;
  is_signal: boolean;
  signal_exclusions: string[];
  snapshot_age_minutes: number;
};

export type OpportunityFilters = {
  minEdge?: number;
  risk?: "low" | "medium" | "high";
  matchday?: number;
  sort?: "edge" | "ev" | "probability";
};

export type PredictionDto = {
  id: string;
  match_id: string;
  model_version_id: string;
  market: string;
  selection: "over" | "under";
  probability: number;
  fair_odds: number;
  implied_probability: number | null;
  no_vig_probability: number | null;
  edge_pp: number | null;
  ev: number | null;
  data_quality: string;
  risk_level: string;
  inputs: string | null;
  inputs_hash: string;
  prediction_timestamp: string;
};

export type TeamMatchStatsDto = {
  match_id: string;
  team_id: string;
  goals: number;
  shots: number | null;
  shots_on_target: number | null;
  possession: number | null;
  corners: number | null;
};

export type MatchDetailDto = {
  match: MatchDto;
  stats: TeamMatchStatsDto[];
  odds: OddsDto[];
  predictions: PredictionDto[];
};

export type OddsDto = {
  match_id: string;
  market: string;
  selection: string;
  decimal_odds: number;
  captured_at: string;
  provider: string;
};

export async function fetchMatchDetail(matchId: string): Promise<MatchDetailDto> {
  const response = await fetch(`/api/v1/matches/${encodeURIComponent(matchId)}`, {
    next: { revalidate: 60 },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }

  return (await response.json()) as MatchDetailDto;
}

export async function fetchOpportunities(filters: OpportunityFilters = {}): Promise<OpportunityDto[]> {
  const params = new URLSearchParams();
  if (filters.minEdge != null) params.set("min_edge", String(filters.minEdge));
  if (filters.risk != null) params.set("risk", filters.risk);
  if (filters.matchday != null) params.set("matchday", String(filters.matchday));
  if (filters.sort != null && filters.sort !== "edge") params.set("sort", filters.sort);

  const query = params.toString();
  const url = `/api/v1/opportunities${query ? `?${query}` : ""}`;

  const response = await fetch(url, {
    next: { revalidate: 60 },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }

  return (await response.json()) as OpportunityDto[];
}
