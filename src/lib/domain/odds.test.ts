import { describe, expect, it } from "vitest";
import {
  edgeInPercentagePoints,
  expectedValue,
  fairOdds,
  impliedProbability,
} from "./odds";

describe("odds domain", () => {
  it("calculates the documented reference values", () => {
    expect(impliedProbability(2)).toBe(0.5);
    expect(fairOdds(0.6)).toBeCloseTo(1.6667, 4);
    expect(expectedValue(0.6, 2)).toBeCloseTo(0.2, 6);
    expect(edgeInPercentagePoints(0.6, 0.5)).toBeCloseTo(10, 6);
  });

  it("rejects invalid inputs", () => {
    expect(() => impliedProbability(1)).toThrow();
    expect(() => fairOdds(0)).toThrow();
    expect(() => edgeInPercentagePoints(1.1, 0.5)).toThrow();
  });
});
