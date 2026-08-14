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
