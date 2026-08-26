// Cliente tipado del API v1. Espeja el OpenAPI canónico en packages/contracts.

// En SSR, fetch exige URL absoluta; en el navegador la relativa pasa por el
// rewrite de Next (/api/v1/*). STATS_API_URL es la misma variable del rewrite.
const SSR_API_BASE = (process.env.STATS_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

function apiUrl(path: string): string {
  if (typeof window === "undefined") {
    return `${SSR_API_BASE}${path}`;
  }
  return path;
}

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

// Devuelve el correlation_id del error (para soporte) o null si no es de API.
export function errorCorrelationId(e: unknown): string | null {
  if (e instanceof ApiError && e.payload.correlation_id) {
    return e.payload.correlation_id;
  }
  return null;
}

// Formateo defensivo: cifras inválidas no se muestran (US4).
export function safeFixed(value: number | null | undefined, digits: number): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function safePct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export async function fetchMatchday(): Promise<MatchdayDto> {
  const response = await fetch(apiUrl("/api/v1/matchdays/current"), {
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
  confidence_level: string;
  confidence_score: number;
  confidence_factors: string[];
  stake_pct: number | null;
  stake_units: number | null;
};

export type OpportunityFilters = {
  minEdge?: number;
  risk?: "low" | "medium" | "high";
  matchday?: number;
  sort?: "edge" | "ev" | "probability";
};

export type SignalExplanation = {
  summary: string;
  factors: string[];
  risks: string[];
  formula: string;
  provenance: {
    dataset: string | null;
    feature_set_version: string | null;
    inputs_hash: string;
  };
  model_version: string | null;
  prediction_timestamp: string;
  is_guarantee: boolean;
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
  snapshot_age_minutes: number | null;
  confidence_level: string | null;
  confidence_score: number | null;
  confidence_factors: string[];
  explanation: SignalExplanation | null;
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
  const response = await fetch(apiUrl(`/api/v1/matches/${encodeURIComponent(matchId)}`), {
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

  const response = await fetch(apiUrl(url), {
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

export async function fetchFeaturedSignals(limit = 3): Promise<OpportunityDto[]> {
  const url = `/api/v1/signals/featured?limit=${limit}`;
  const response = await fetch(apiUrl(url), { next: { revalidate: 60 } });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }

  return (await response.json()) as OpportunityDto[];
}

export type ParlaySelectionRef = {
  match_id: string;
  market: string;
  selection: "over" | "under";
};

export type ResolvedSelectionDto = {
  key: string;
  match_id: string;
  market: string;
  selection: "over" | "under";
  home_team_short: string;
  away_team_short: string;
  kickoff_at: string;
  probability: number;
  odds: number;
  fair_odds: number;
  edge_pp: number;
  data_quality: string;
  risk_level: string;
  confidence_level: string;
  confidence_score: number;
  confidence_factors: string[];
  stake_pct: number | null;
  stake_units: number | null;
};

export type ParlayEstimateDto = {
  selections: ResolvedSelectionDto[];
  combined_odds: number;
  naive_probability: number;
  estimated_probability: number;
  fair_combined_odds: number | null;
  risk_level: string;
  risk_factors: string[];
  correlation_warnings: string[];
  assumes_independence: boolean;
  selection_count: number;
  stake_pct: number | null;
  stake_units: number | null;
};

export async function estimateParlay(selections: ParlaySelectionRef[]): Promise<ParlayEstimateDto> {
  const response = await fetch(apiUrl("/api/v1/parlays/estimate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selections }),
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }

  return (await response.json()) as ParlayEstimateDto;
}

export type ModelVersionDto = {
  id: string;
  name: string;
  version: string;
  status: string;
  feature_set_version: string;
  created_at: string;
};

export type CalibrationBinDto = {
  label: string;
  lower: number;
  upper: number;
  n: number;
  mean_predicted: number | null;
  observed_rate: number | null;
};

export type MetricsDto = {
  model_version_id: string | null;
  sample_size: number;
  wins: number;
  losses: number;
  voids: number;
  hit_rate: number | null;
  unit_roi: number | null;
  brier: number | null;
  calibration_bins: CalibrationBinDto[];
  sample_sufficient: boolean;
  threshold: number;
};

export type HistoryItemDto = {
  prediction_id: string;
  match_id: string;
  home_team_short: string;
  away_team_short: string;
  kickoff_at: string;
  market: string;
  selection: string;
  probability: number;
  odds: number | null;
  model_version: string;
  prediction_timestamp: string;
  result: "win" | "loss" | "void";
  resolved_at: string;
};

export type HistoryPageDto = {
  items: HistoryItemDto[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type HistoryFilters = {
  modelVersion?: string;
  result?: "win" | "loss" | "void";
  matchday?: number;
  page?: number;
  pageSize?: number;
};

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(url), init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ErrorDto | null;
    throw new ApiError(
      response.status,
      payload ?? { code: "unknown", message: response.statusText, details: null, correlation_id: "" },
    );
  }
  return (await response.json()) as T;
}

export function fetchModelVersions(): Promise<ModelVersionDto[]> {
  return getJson<ModelVersionDto[]>("/api/v1/model-versions", { next: { revalidate: 60 } });
}

export function fetchMetrics(modelVersionId?: string): Promise<MetricsDto> {
  const query = modelVersionId ? `?model_version_id=${encodeURIComponent(modelVersionId)}` : "";
  return getJson<MetricsDto>(`/api/v1/metrics${query}`, { next: { revalidate: 60 } });
}

export function fetchHistory(filters: HistoryFilters = {}): Promise<HistoryPageDto> {
  const params = new URLSearchParams();
  if (filters.modelVersion != null && filters.modelVersion !== "") params.set("model_version", filters.modelVersion);
  if (filters.result != null) params.set("result", filters.result);
  if (filters.matchday != null) params.set("matchday", String(filters.matchday));
  if (filters.page != null && filters.page > 1) params.set("page", String(filters.page));
  if (filters.pageSize != null && filters.pageSize !== 20) params.set("page_size", String(filters.pageSize));
  const query = params.toString();
  return getJson<HistoryPageDto>(`/api/v1/history${query ? `?${query}` : ""}`, { next: { revalidate: 30 } });
}
