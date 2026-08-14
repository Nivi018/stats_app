import { describe, expect, it, vi, afterEach } from "vitest";
import { ApiError, fetchMatchday, fetchOpportunities } from "@/lib/api/client";

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
