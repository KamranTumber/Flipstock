import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownWideNarrow, Bookmark, LayoutGrid, Loader2, Moon, Radar, Rows3, Settings, Sun, TrendingUp } from "lucide-react";
import { api, streamSearch } from "./api";
import type { Deal, Health, Preset, SearchParams, SearchResponse, SourceStatus, UserSettings, WatchlistItem } from "./types";
import SearchPanel from "./components/SearchPanel";
import StatusBar from "./components/StatusBar";
import DealCard from "./components/DealCard";
import DealTable from "./components/DealTable";
import BreakdownModal from "./components/BreakdownModal";
import Watchlist from "./components/Watchlist";
import SettingsPanel from "./components/SettingsPanel";
import { gbp0 } from "./format";

type Tab = "deals" | "watchlist" | "settings";
type SortKey = "profit" | "roi" | "distance" | "newest";

const DEFAULT_PARAMS: SearchParams = {
  q: "",
  preset: "",
  postcode: "",
  radius: 25,
  min_profit: 20,
  min_roi: 15,
  sources: ["ebay", "gumtree", "facebook"],
  include_flagged: false,
  include_below_threshold: false,
  demo: false,
};

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? { ...fallback, ...JSON.parse(v) } : fallback;
  } catch {
    return fallback;
  }
}

export default function App() {
  const [tab, setTab] = useState<Tab>("deals");
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [params, setParams] = useState<SearchParams>(() => load("fs-params", DEFAULT_PARAMS));
  const [presets, setPresets] = useState<Preset[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [watch, setWatch] = useState<WatchlistItem[]>([]);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("");
  const [statuses, setStatuses] = useState<SourceStatus[]>([]);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<SortKey>("profit");
  const [view, setView] = useState<"grid" | "table">(() => (localStorage.getItem("fs-view") as "grid" | "table") || "grid");
  const [detail, setDetail] = useState<Deal | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("fs-theme", dark ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }, [dark]);

  useEffect(() => {
    try {
      localStorage.setItem("fs-params", JSON.stringify(params));
      localStorage.setItem("fs-view", view);
    } catch {
      /* ignore */
    }
  }, [params, view]);

  useEffect(() => {
    api.presets().then(setPresets).catch(() => setError("Cannot reach the backend at /api — start it with ./start.sh (or start.ps1)."));
    api.health().then(setHealth).catch(() => {});
    api.watchlist().then(setWatch).catch(() => {});
    api
      .settings()
      .then((s) => {
        setSettings(s);
        setParams((p) =>
          p.postcode ? p : { ...p, postcode: s.default_postcode, radius: s.default_radius, min_profit: s.default_min_profit, min_roi: s.default_min_roi },
        );
      })
      .catch(() => {});
  }, []);

  const runSearch = useCallback(() => {
    cancelRef.current?.();
    setRunning(true);
    setError("");
    setStatuses([]);
    setStage("Starting…");
    cancelRef.current = streamSearch(params, {
      onStage: setStage,
      onSource: (s) => setStatuses((prev) => [...prev.filter((x) => x.source !== s.source), s]),
      onResult: (r) => {
        setResult(r);
        setStatuses(r.statuses);
        setRunning(false);
        setStage("");
      },
      onError: (m) => {
        setError(m);
        setRunning(false);
        setStage("");
      },
    });
  }, [params]);

  const cancel = () => {
    cancelRef.current?.();
    setRunning(false);
    setStage("");
  };

  const watchedIds = useMemo(() => new Set(watch.map((w) => w.listing_id)), [watch]);

  const toggleWatch = async (d: Deal) => {
    const existing = watch.find((w) => w.listing_id === d.listing.id);
    try {
      if (existing) {
        await api.unwatch(existing.id);
        setWatch((w) => w.filter((x) => x.id !== existing.id));
      } else {
        const item = await api.watch(d);
        setWatch((w) => [item, ...w]);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const sorted = useMemo(() => {
    if (!result) return [];
    const ds = result.deals.map((d, i) => ({ d, i }));
    const cmp: Record<SortKey, (a: { d: Deal; i: number }, b: { d: Deal; i: number }) => number> = {
      profit: (a, b) => (b.d.best_profit ?? -1e9) - (a.d.best_profit ?? -1e9),
      roi: (a, b) => (b.d.best_roi ?? -1e9) - (a.d.best_roi ?? -1e9),
      distance: (a, b) => (a.d.listing.distance_miles ?? 1e9) - (b.d.listing.distance_miles ?? 1e9),
      newest: (a, b) => a.i - b.i,
    };
    return ds.sort(cmp[sort]).map((x) => x.d);
  }, [result, sort]);

  const totalProfit = sorted.reduce((a, d) => a + Math.max(0, d.best_profit ?? 0), 0);

  const TabBtn = ({ id, label, Icon, count }: { id: Tab; label: string; Icon: typeof Radar; count?: number }) => (
    <button
      onClick={() => setTab(id)}
      className={`btn-ghost ${tab === id ? "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white" : ""}`}
      aria-current={tab === id}
    >
      <Icon className="h-4 w-4" /> <span className="hidden sm:inline">{label}</span>
      {count ? <span className="rounded-full bg-emerald-600 px-1.5 text-[10px] font-bold text-white">{count}</span> : null}
    </button>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-2.5">
          <div className="mr-2 flex items-center gap-2">
            <div className="rounded-lg bg-emerald-600 p-1.5 text-white">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <div className="font-bold">FlipScout UK</div>
              <div className="hidden text-[11px] text-slate-500 sm:block">Electronics arbitrage · eBay · Gumtree · FB · CeX</div>
            </div>
          </div>
          <nav className="flex gap-1">
            <TabBtn id="deals" label="Deals" Icon={Radar} />
            <TabBtn id="watchlist" label="Saved flips" Icon={Bookmark} count={watch.length} />
            <TabBtn id="settings" label="Settings" Icon={Settings} />
          </nav>
          <button className="btn-ghost ml-auto p-2" onClick={() => setDark((d) => !d)} aria-label="Toggle dark mode">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-4">
        {error && (
          <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">{error}</div>
        )}

        {tab === "deals" && (
          <>
            <SearchPanel params={params} presets={presets} running={running} onChange={setParams} onSearch={runSearch} onCancel={cancel} />

            {(running || statuses.length > 0) && (
              <div className="space-y-2">
                {running && (
                  <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-600" /> {stage}
                  </div>
                )}
                <StatusBar statuses={statuses} />
              </div>
            )}

            {result && !running && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <span>
                  <b>{sorted.length}</b> deal{sorted.length === 1 ? "" : "s"} from {result.total_listings} listings near <b>{result.geo.postcode}</b>
                  {result.geo.district ? ` (${result.geo.district})` : ""} · {(result.elapsed_ms / 1000).toFixed(1)}s
                </span>
                {totalProfit > 0 && <span className="text-emerald-600 dark:text-emerald-400">Combined best-exit profit {gbp0(totalProfit)}</span>}
                <span className="text-xs text-slate-500">
                  hidden: {result.flagged_hidden} red-flag · {result.below_threshold_hidden} below threshold · {result.out_of_radius_hidden} out of radius
                </span>
                <div className="ml-auto flex items-center gap-2">
                  <ArrowDownWideNarrow className="h-4 w-4 text-slate-400" />
                  <select className="input w-auto py-1" value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort">
                    <option value="profit">Net profit (£)</option>
                    <option value="roi">ROI (%)</option>
                    <option value="distance">Distance</option>
                    <option value="newest">Newly listed</option>
                  </select>
                  <div className="flex rounded-lg border border-slate-300 dark:border-slate-700">
                    <button className={`p-1.5 ${view === "grid" ? "bg-slate-100 dark:bg-slate-800" : ""}`} onClick={() => setView("grid")} aria-label="Grid view">
                      <LayoutGrid className="h-4 w-4" />
                    </button>
                    <button className={`p-1.5 ${view === "table" ? "bg-slate-100 dark:bg-slate-800" : ""}`} onClick={() => setView("table")} aria-label="Table view">
                      <Rows3 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {result && !running && sorted.length === 0 && (
              <div className="card p-8 text-center text-sm text-slate-500">
                No deals met your thresholds. Try lowering min profit / ROI, widening the radius, or tick “Show below threshold”.
              </div>
            )}

            {sorted.length > 0 &&
              (view === "grid" ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {sorted.map((d) => (
                    <DealCard key={d.listing.id} deal={d} watched={watchedIds.has(d.listing.id)} onWatch={toggleWatch} onDetails={setDetail} />
                  ))}
                </div>
              ) : (
                <DealTable deals={sorted} watched={watchedIds} onWatch={toggleWatch} onDetails={setDetail} />
              ))}

            {!result && !running && (
              <div className="card p-8 text-center text-sm text-slate-500">
                Enter a search (or pick a preset) and your postcode. FlipScout searches eBay, Gumtree and FB Marketplace in parallel, then values each item against
                eBay sold prices, CeX trade-in offers and local FB prices.
                {!health?.ebay_api && (
                  <p className="mt-2 text-xs">Tip: eBay often refuses automated requests — add free eBay API keys in Settings, or tick “Demo data” to explore.</p>
                )}
              </div>
            )}
          </>
        )}

        {tab === "watchlist" && (
          <Watchlist
            items={watch}
            onDetails={setDetail}
            onDelete={async (id) => {
              await api.unwatch(id);
              setWatch((w) => w.filter((x) => x.id !== id));
            }}
            onUpdate={async (id, patch) => {
              const upd = await api.updateWatch(id, patch);
              setWatch((w) => w.map((x) => (x.id === id ? upd : x)));
            }}
          />
        )}

        {tab === "settings" && (
          <SettingsPanel
            settings={settings}
            health={health}
            onSave={async (s) => {
              const saved = await api.saveSettings(s);
              setSettings(saved);
              api.health().then(setHealth).catch(() => {});
            }}
          />
        )}
      </main>

      {detail && <BreakdownModal deal={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
