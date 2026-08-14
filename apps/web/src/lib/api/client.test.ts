import { describe, expect, it, vi, afterEach } from "vitest";
import { ApiError, fetchMatchday } from "@/lib/api/client";

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
