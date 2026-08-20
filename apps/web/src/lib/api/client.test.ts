import { describe, expect, it, vi, afterEach } from "vitest";
import {
  ApiError,
  errorCorrelationId,
  fetchMatchday,
  fetchMatchDetail,
  fetchOpportunities,
  safeFixed,
  safePct,
} from "@/lib/api/client";

const matchdayFixture = {
  matchday: 1,
  updated_at: "2026-08-11T08:00:00Z",
  total_matches: 1,
  matches: [
    {
      id: "match-up-01",
      competition: "Liga MX",
      kickoff_at: "2026-08-03T17:00:00Z",
      home_team: { id: "mx-ame", name: "Club América", short_name: "AME" },
      away_team: { id: "mx-caz", name: "Cruz Azul", short_name: "CAZ" },
      status: "scheduled",
      over_odds: 1.9,
      under_odds: 1.95,
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchMatchday", () => {
  it("returns parsed matchday on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => matchdayFixture,
      }),
    );

    const result = await fetchMatchday();
    expect(result.matchday).toBe(1);
    expect(result.matches[0].home_team.short_name).toBe("AME");
    expect(result.matches[0].over_odds).toBe(1.9);
  });

  it("throws ApiError with correlation_id on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({
          code: "internal_error",
          message: "Error interno del servidor",
          details: null,
          correlation_id: "abc-123",
        }),
      }),
    );

    const promise = fetchMatchday();
    await expect(promise).rejects.toThrow(ApiError);
    await expect(promise).rejects.toMatchObject({ status: 500 });
  });

  it("throws ApiError when response is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        json: async () => {
          throw new SyntaxError("not json");
        },
      }),
    );

    const promise = fetchMatchday();
    await expect(promise).rejects.toThrow(ApiError);
    await expect(promise).rejects.toMatchObject({ status: 502 });
  });
});

describe("fetchOpportunities", () => {
  it("returns parsed opportunities with signal flag", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            match_id: "match-up-01",
            home_team_short: "AME",
            away_team_short: "CAZ",
            kickoff_at: "2026-08-03T17:00:00Z",
            market: "over_under_2_5",
            selection: "over",
            model_probability: 0.6,
            market_no_vig_probability: 0.5,
            observed_odds: 2.0,
            fair_odds: 1.6667,
            edge_pp: 10,
            ev: 0.2,
            data_quality: "high",
            risk_level: "low",
            is_signal: true,
            signal_exclusions: [],
            snapshot_age_minutes: 5,
          },
        ],
      }),
    );

    const result = await fetchOpportunities();
    expect(result).toHaveLength(1);
    expect(result[0].is_signal).toBe(true);
    expect(result[0].edge_pp).toBe(10);
  });

  it("throws ApiError on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Error",
        json: async () => ({ code: "internal_error", message: "boom", details: null, correlation_id: "x" }),
      }),
    );

    await expect(fetchOpportunities()).rejects.toThrow(ApiError);
  });

  it("passes filters as query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);

    await fetchOpportunities({ minEdge: 5, risk: "low", matchday: 1, sort: "ev" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("min_edge=5");
    expect(calledUrl).toContain("risk=low");
    expect(calledUrl).toContain("matchday=1");
    expect(calledUrl).toContain("sort=ev");
  });

  it("omits sort when default edge", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);

    await fetchOpportunities({ sort: "edge" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("sort=");
  });
});

describe("fetchMatchDetail", () => {
  it("requests the match detail URL and parses predictions", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        match: {
          id: "match-up-01",
          competition: "Liga MX",
          kickoff_at: "2026-08-03T17:00:00Z",
          home_team: { id: "mx-ame", name: "Club América", short_name: "AME" },
          away_team: { id: "mx-caz", name: "Cruz Azul", short_name: "CAZ" },
          status: "scheduled",
          over_odds: 1.9,
          under_odds: 1.95,
        },
        stats: [],
        odds: [],
        predictions: [
          {
            id: "p1",
            match_id: "m",
            model_version_id: "mv",
            market: "over_under_2_5",
            selection: "over",
            probability: 0.6,
            fair_odds: 1.6667,
            implied_probability: null,
            no_vig_probability: null,
            edge_pp: null,
            ev: null,
            data_quality: "high",
            risk_level: "low",
            inputs: '{"model_version":"1.0.0"}',
            inputs_hash: "abc",
            prediction_timestamp: "2026-08-11T08:00:00Z",
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchMatchDetail("match-up-01");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/matches/match-up-01");
    expect(result.predictions).toHaveLength(1);
    expect(result.predictions[0].probability).toBe(0.6);
  });
});

describe("US4 helpers", () => {
  it("exposes the correlation_id of an ApiError for support", () => {
    const error = new ApiError(500, {
      code: "internal_error",
      message: "boom",
      details: null,
      correlation_id: "corr-for-support",
    });
    expect(errorCorrelationId(error)).toBe("corr-for-support");
    expect(errorCorrelationId(new Error("otro"))).toBeNull();
    expect(errorCorrelationId(null)).toBeNull();
  });

  it("does not render invalid figures (cifras inválidas)", () => {
    expect(safePct(null)).toBe("—");
    expect(safePct(undefined)).toBe("—");
    expect(safePct(Number.NaN)).toBe("—");
    expect(safePct(1.5)).toBe("—");
    expect(safePct(0.6)).toBe("60.0%");
    expect(safeFixed(Number.POSITIVE_INFINITY, 2)).toBe("—");
    expect(safeFixed(1.85, 2)).toBe("1.85");
  });
});
