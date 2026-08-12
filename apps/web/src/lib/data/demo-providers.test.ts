import { describe, expect, it } from "vitest";
import {
  DEMO_MATCHES,
  DEMO_ODDS,
  DEMO_STATS,
  DemoOddsProvider,
  DemoSportsDataProvider,
} from "./demo-providers";

describe("demo dataset", () => {
  it("creates 12 teams referenced in matches", () => {
    const teamIds = new Set<string>();
    for (const m of DEMO_MATCHES) {
      teamIds.add(m.homeTeam.id);
      teamIds.add(m.awayTeam.id);
    }
    expect(teamIds.size).toBe(12);
  });

  it("has 30 historical and 12 upcoming matches", () => {
    const historical = DEMO_MATCHES.filter((m) => m.status === "finished");
    const upcoming = DEMO_MATCHES.filter((m) => m.status === "scheduled");
    expect(historical.length).toBe(30);
    expect(upcoming.length).toBe(12);
  });

  it("produces 2 team stats per historical match", () => {
    expect(DEMO_STATS.length).toBe(60);
  });

  it("produces exactly 2 odds snapshots per upcoming match", () => {
    expect(DEMO_ODDS.length).toBe(24);
  });
});

describe("DemoSportsDataProvider", () => {
  const provider = new DemoSportsDataProvider();

  it("returns 12 upcoming matches", async () => {
    const matches = await provider.getUpcomingMatches();
    expect(matches.length).toBe(12);
    for (const m of matches) {
      expect(m.status).toBe("scheduled");
    }
  });

  it("finds an existing match by id", async () => {
    const target = DEMO_MATCHES[0];
    const match = await provider.getMatch(target.id);
    expect(match).not.toBeNull();
    expect(match!.id).toBe(target.id);
  });

  it("returns null for an unknown id", async () => {
    const match = await provider.getMatch("nonexistent");
    expect(match).toBeNull();
  });

  it("returns stats for a historical match", async () => {
    const hist = DEMO_MATCHES.find((m) => m.status === "finished")!;
    const stats = await provider.getTeamMatchStats(hist.id);
    expect(stats.length).toBe(2);
  });
});

describe("DemoOddsProvider", () => {
  const provider = new DemoOddsProvider();

  it("returns odds for an upcoming match", async () => {
    const upcoming = DEMO_MATCHES.find((m) => m.status === "scheduled")!;
    const odds = await provider.getOddsSnapshots(upcoming.id);
    expect(odds.length).toBe(2);
    const markets = odds.map((o) => o.selection).sort();
    expect(markets).toEqual(["over", "under"]);
  });

  it("returns empty array for a historical match", async () => {
    const hist = DEMO_MATCHES.find((m) => m.status === "finished")!;
    const odds = await provider.getOddsSnapshots(hist.id);
    expect(odds.length).toBe(0);
  });
});
