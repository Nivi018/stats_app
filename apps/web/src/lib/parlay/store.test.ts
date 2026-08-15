import { describe, expect, it } from "vitest";
import {
  PARLAY_MAX,
  PARLAY_MIN,
  addSelection,
  canonicalKey,
  clearKeys,
  count,
  emptyParlay,
  fromKeys,
  hasSelection,
  isFull,
  loadKeys,
  parseKey,
  removeSelection,
  replaceSelection,
  saveKeys,
  toKeys,
  type KeyValueStorage,
  type ParlaySelection,
  type ParlayState,
} from "./store";

function memoryStorage(initial: Record<string, string> = {}): KeyValueStorage & { entries: () => Record<string, string> } {
  const data = { ...initial };
  return {
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = value;
    },
    removeItem: (key) => {
      delete data[key];
    },
    entries: () => ({ ...data }),
  };
}

const sel = (matchId: string, selection: "over" | "under" = "over"): Omit<ParlaySelection, "key"> => ({
  match_id: matchId,
  market: "over_under_2_5",
  selection,
});

describe("parlay store", () => {
  it("construye y parsea el ID canónico", () => {
    expect(canonicalKey("match-up-01", "over_under_2_5", "over")).toBe(
      "match-up-01::over_under_2_5::over",
    );
    expect(parseKey("match-up-01::over_under_2_5::over")).toEqual({
      match_id: "match-up-01",
      market: "over_under_2_5",
      selection: "over",
    });
    expect(() => parseKey("invalido")).toThrow();
    expect(() => parseKey("a::b::draw")).toThrow();
  });

  it("añade selecciones y evita duplicados", () => {
    let state: ParlayState = emptyParlay();
    expect(count(state)).toBe(0);

    const first = addSelection(state, sel("match-up-01"));
    expect(first.result).toBe("added");
    expect(first.state).toHaveLength(1);
    state = first.state;

    const dup = addSelection(state, sel("match-up-01"));
    expect(dup.result).toBe("duplicate");
    expect(dup.state).toHaveLength(1); // no muta

    const second = addSelection(state, sel("match-up-02"));
    expect(second.result).toBe("added");
    expect(count(second.state)).toBe(2);
  });

  it("valida el límite de 2-3 selecciones", () => {
    expect(PARLAY_MIN).toBe(2);
    expect(PARLAY_MAX).toBe(3);

    let state = addSelection(emptyParlay(), sel("match-up-01")).state;
    state = addSelection(state, sel("match-up-02")).state;
    expect(isFull(state)).toBe(false);

    state = addSelection(state, sel("match-up-03")).state;
    expect(count(state)).toBe(3);
    expect(isFull(state)).toBe(true);

    const overflow = addSelection(state, sel("match-up-04"));
    expect(overflow.result).toBe("full");
    expect(overflow.state).toHaveLength(3);
  });

  it("retira una selección sin afectar al resto", () => {
    let state = addSelection(emptyParlay(), sel("match-up-01")).state;
    state = addSelection(state, sel("match-up-02")).state;
    state = addSelection(state, sel("match-up-03")).state;

    const next = removeSelection(state, canonicalKey("match-up-02", "over_under_2_5", "over"));
    expect(next).toHaveLength(2);
    expect(next.some((s) => s.match_id === "match-up-02")).toBe(false);
    expect(next.some((s) => s.match_id === "match-up-01")).toBe(true);

    expect(removeSelection(next, "no-existe")).toHaveLength(2);
  });

  it("sustituye una selección por otra", () => {
    let state = addSelection(emptyParlay(), sel("match-up-01")).state;
    state = addSelection(state, sel("match-up-02")).state;

    const replaced = replaceSelection(state, canonicalKey("match-up-01", "over_under_2_5", "over"), sel("match-up-05"));
    expect(replaced.result).toBe("replaced");
    expect(count(replaced.state)).toBe(2);
    expect(replaced.state.some((s) => s.match_id === "match-up-05")).toBe(true);
    expect(replaced.state.some((s) => s.match_id === "match-up-01")).toBe(false);

    expect(replaceSelection(state, "ausente", sel("match-up-05")).result).toBe("not_found");
    expect(replaceSelection(state, canonicalKey("match-up-01", "over_under_2_5", "over"), sel("match-up-02")).result).toBe("duplicate");
  });

  it("se reconstruye desde IDs canónicos", () => {
    let state = addSelection(emptyParlay(), sel("match-up-01", "over")).state;
    state = addSelection(state, sel("match-up-02", "under")).state;

    const keys = toKeys(state);
    const rebuilt = fromKeys(keys);
    expect(rebuilt).toEqual(state);
  });

  it("reconstrucción defensiva: descarta IDs corruptos y duplicados", () => {
    const rebuilt = fromKeys([
      "match-up-01::over_under_2_5::over",
      "basura",
      "match-up-01::over_under_2_5::over", // duplicado
      "match-up-02::over_under_2_5::under",
    ]);
    expect(rebuilt).toHaveLength(2);
    expect(rebuilt[0].match_id).toBe("match-up-01");
  });

  it("persiste y recarga en almacenamiento de sesión", () => {
    const storage = memoryStorage();
    let state = addSelection(emptyParlay(), sel("match-up-01")).state;
    state = addSelection(state, sel("match-up-02", "under")).state;

    saveKeys(toKeys(state), storage);
    const loaded = fromKeys(loadKeys(storage));
    expect(loaded).toEqual(state);

    clearKeys(storage);
    expect(loadKeys(storage)).toEqual([]);
  });

  it("tolera almacenamiento corrupto", () => {
    const storage = memoryStorage({ "stats:parlay:selections": "no-json{" });
    expect(loadKeys(storage)).toEqual([]);

    const notArray = memoryStorage({ "stats:parlay:selections": '{"a":1}' });
    expect(loadKeys(notArray)).toEqual([]);
  });

  it("expone hasSelection", () => {
    const state = addSelection(emptyParlay(), sel("match-up-01")).state;
    expect(hasSelection(state, canonicalKey("match-up-01", "over_under_2_5", "over"))).toBe(true);
    expect(hasSelection(state, canonicalKey("match-up-09", "over_under_2_5", "over"))).toBe(false);
  });
});
