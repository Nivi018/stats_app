// Estado del constructor de parlay (US1).
//
// El estado se expresa como una lista ordenada de selecciones; cada selección
// queda identificada por su ID canónico (`match_id::market::selection`), de modo
// que el ticket puede reconstruirse desde los IDs canónicos aunque se pierdan
// los datos de presentación. Las funciones son puras e inmutables.

export const PARLAY_MIN = 2;
export const PARLAY_MAX = 3;
export const PARLAY_STORAGE_KEY = "stats:parlay:selections";

export type SelectionName = "over" | "under";

export type ParlaySelection = {
  key: string;
  match_id: string;
  market: string;
  selection: SelectionName;
};

export type ParlayState = readonly ParlaySelection[];

export type AddResult = "added" | "duplicate" | "full";

export type ReplaceResult = "replaced" | "not_found" | "duplicate" | "full";

export function canonicalKey(
  matchId: string,
  market: string,
  selection: SelectionName,
): string {
  return `${matchId}::${market}::${selection}`;
}

export function parseKey(key: string): Omit<ParlaySelection, "key"> {
  const parts = key.split("::");
  if (parts.length !== 3 || parts.some((p) => p.length === 0)) {
    throw new Error(`ID canónico de parlay inválido: ${key}`);
  }
  const [match_id, market, rawSelection] = parts;
  const selection = rawSelection as SelectionName;
  if (selection !== "over" && selection !== "under") {
    throw new Error(`Selección desconocida en ID canónico: ${key}`);
  }
  return { match_id, market, selection };
}

export function toSelection(selection: Omit<ParlaySelection, "key">): ParlaySelection {
  return { ...selection, key: canonicalKey(selection.match_id, selection.market, selection.selection) };
}

export function emptyParlay(): ParlayState {
  return [];
}

export function count(state: ParlayState): number {
  return state.length;
}

export function isFull(state: ParlayState, max: number = PARLAY_MAX): boolean {
  return state.length >= max;
}

export function hasSelection(state: ParlayState, key: string): boolean {
  return state.some((s) => s.key === key);
}

export function addSelection(state: ParlayState, raw: Omit<ParlaySelection, "key">): { state: ParlayState; result: AddResult } {
  const selection = toSelection(raw);
  if (hasSelection(state, selection.key)) {
    return { state, result: "duplicate" };
  }
  if (isFull(state)) {
    return { state, result: "full" };
  }
  return { state: [...state, selection], result: "added" };
}

export function removeSelection(state: ParlayState, key: string): ParlayState {
  return state.filter((s) => s.key !== key);
}

export function replaceSelection(
  state: ParlayState,
  oldKey: string,
  raw: Omit<ParlaySelection, "key">,
): { state: ParlayState; result: ReplaceResult } {
  if (!hasSelection(state, oldKey)) {
    return { state, result: "not_found" };
  }
  const replacement = toSelection(raw);
  if (replacement.key !== oldKey && hasSelection(state, replacement.key)) {
    return { state, result: "duplicate" };
  }
  const next = state.map((s) => (s.key === oldKey ? replacement : s));
  return { state: next, result: "replaced" };
}

export function toKeys(state: ParlayState): string[] {
  return state.map((s) => s.key);
}

export function fromKeys(keys: string[]): ParlayState {
  const seen = new Set<string>();
  const state: ParlaySelection[] = [];
  for (const key of keys) {
    let parsed: Omit<ParlaySelection, "key">;
    try {
      parsed = parseKey(key);
    } catch {
      continue; // IDs corruptos no bloquean la reconstrucción
    }
    if (seen.has(key)) continue; // dedupe defensivo
    seen.add(key);
    if (state.length >= PARLAY_MAX) break;
    state.push(toSelection(parsed));
  }
  return state;
}

// Persistencia de sesión con inyección de almacenamiento para poder probarlo.
export type KeyValueStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function saveKeys(keys: string[], storage: KeyValueStorage): void {
  storage.setItem(PARLAY_STORAGE_KEY, JSON.stringify(keys));
}

export function loadKeys(storage: KeyValueStorage): string[] {
  const raw = storage.getItem(PARLAY_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((k): k is string => typeof k === "string");
  } catch {
    return [];
  }
}

export function clearKeys(storage: KeyValueStorage): void {
  storage.removeItem(PARLAY_STORAGE_KEY);
}
