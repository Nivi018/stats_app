export function impliedProbability(decimalOdds: number): number {
  if (!Number.isFinite(decimalOdds) || decimalOdds <= 1) {
    throw new Error("Decimal odds must be greater than 1.");
  }

  return 1 / decimalOdds;
}

export function fairOdds(probability: number): number {
  if (!Number.isFinite(probability) || probability <= 0 || probability > 1) {
    throw new Error("Probability must be greater than 0 and at most 1.");
  }

  return 1 / probability;
}

export function expectedValue(
  probability: number,
  decimalOdds: number,
): number {
  return probability * decimalOdds - 1;
}

export function edgeInPercentagePoints(
  modelProbability: number,
  marketProbability: number,
): number {
  if (
    !Number.isFinite(modelProbability) ||
    !Number.isFinite(marketProbability) ||
    modelProbability < 0 ||
    modelProbability > 1 ||
    marketProbability < 0 ||
    marketProbability > 1
  ) {
    throw new Error("Probabilities must be between 0 and 1.");
  }

  return (modelProbability - marketProbability) * 100;
}
