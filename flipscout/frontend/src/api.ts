import type { Deal, EbayTestResult, Health, Preset, SearchParams, SearchResponse, SourceStatus, UserSettings, WatchlistItem, WatchStatus } from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  health: () => fetch("/api/health").then(j<Health>),
  presets: () => fetch("/api/presets").then(j<Preset[]>),
  settings: () => fetch("/api/settings").then(j<UserSettings>),
  saveSettings: (s: UserSettings) =>
    fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s) }).then(j<UserSettings>),
  testEbay: () => fetch("/api/ebay/test", { method: "POST" }).then(j<EbayTestResult>),
  watchlist: () => fetch("/api/watchlist").then(j<WatchlistItem[]>),
  watch: (deal: Deal, notes = "") =>
    fetch("/api/watchlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ deal, notes }) }).then(
      j<WatchlistItem>,
    ),
  updateWatch: (id: number, patch: Partial<{ status: WatchStatus; notes: string; actual_buy_price: number | null; actual_sale_price: number | null }>) =>
    fetch(`/api/watchlist/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }).then(
      j<WatchlistItem>,
    ),
  unwatch: (id: number) => fetch(`/api/watchlist/${id}`, { method: "DELETE" }).then(j<void>),
};

export interface StreamHandlers {
  onStage: (message: string) => void;
  onSource: (s: SourceStatus) => void;
  onResult: (r: SearchResponse) => void;
  onError: (message: string) => void;
}

/** Runs a search over Server-Sent Events. Returns a cancel function. */
export function streamSearch(p: SearchParams, h: StreamHandlers): () => void {
  const qs = new URLSearchParams({
    q: p.q,
    preset: p.preset,
    postcode: p.postcode,
    radius: String(p.radius),
    min_profit: String(p.min_profit),
    min_roi: String(p.min_roi),
    sources: p.sources.join(","),
    include_flagged: String(p.include_flagged),
    include_below_threshold: String(p.include_below_threshold),
    demo: String(p.demo),
  });
  const es = new EventSource(`/api/search/stream?${qs}`);
  let finished = false;
  es.onmessage = (ev) => {
    const evt = JSON.parse(ev.data);
    if (evt.type === "stage") h.onStage(evt.message);
    else if (evt.type === "source") h.onSource(evt.status);
    else if (evt.type === "result") {
      finished = true;
      h.onResult(evt.data);
    } else if (evt.type === "error") {
      finished = true;
      h.onError(evt.message);
    }
  };
  es.addEventListener("done", () => es.close());
  es.onerror = () => {
    es.close();
    if (!finished) h.onError("Lost connection to the FlipScout backend — is it running on port 8000?");
  };
  return () => es.close();
}
