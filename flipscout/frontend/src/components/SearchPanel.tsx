import { Loader2, MapPin, Search, Square } from "lucide-react";
import type { Preset, SearchParams, SourceName } from "../types";

const RADII = [5, 10, 25, 50, 0];
const SOURCES: { id: SourceName; label: string }[] = [
  { id: "ebay", label: "eBay UK" },
  { id: "gumtree", label: "Gumtree" },
  { id: "facebook", label: "FB Marketplace" },
];

interface Props {
  params: SearchParams;
  presets: Preset[];
  running: boolean;
  onChange: (p: SearchParams) => void;
  onSearch: () => void;
  onCancel: () => void;
}

export default function SearchPanel({ params, presets, running, onChange, onSearch, onCancel }: Props) {
  const set = <K extends keyof SearchParams>(k: K, v: SearchParams[K]) => onChange({ ...params, [k]: v });
  const toggleSource = (s: SourceName) =>
    set("sources", params.sources.includes(s) ? params.sources.filter((x) => x !== s) : [...params.sources, s]);
  const preset = presets.find((p) => p.id === params.preset);

  return (
    <form
      className="card p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!running) onSearch();
      }}
    >
      <div className="grid gap-3 md:grid-cols-12">
        <div className="md:col-span-5">
          <label className="label" htmlFor="q">
            Search
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="q"
              className="input pl-9"
              placeholder={preset ? `Preset: ${preset.queries.join(", ")}` : "e.g. RTX 3080, PS5 console, iPhone 13"}
              value={params.q}
              onChange={(e) => set("q", e.target.value)}
            />
          </div>
        </div>
        <div className="md:col-span-3">
          <label className="label" htmlFor="pc">
            Postcode
          </label>
          <div className="relative">
            <MapPin className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              id="pc"
              className="input pl-9 uppercase"
              placeholder="RH19 1AA"
              value={params.postcode}
              onChange={(e) => set("postcode", e.target.value.toUpperCase())}
              required
            />
          </div>
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="radius">
            Radius
          </label>
          <select id="radius" className="input" value={params.radius} onChange={(e) => set("radius", Number(e.target.value))}>
            {RADII.map((r) => (
              <option key={r} value={r}>
                {r === 0 ? "Nationwide" : `${r} miles`}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end md:col-span-2">
          {running ? (
            <button type="button" className="btn-ghost w-full border border-slate-300 dark:border-slate-700" onClick={onCancel}>
              <Square className="h-4 w-4" /> Stop
            </button>
          ) : (
            <button type="submit" className="btn-primary w-full">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Find deals
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="label mb-0 mr-1">Presets</span>
        {presets.map((p) => (
          <button
            type="button"
            key={p.id}
            onClick={() => set("preset", params.preset === p.id ? "" : p.id)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              params.preset === p.id
                ? "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                : "border-slate-300 text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:text-slate-300"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
        <div className="lg:col-span-2">
          <label className="label" htmlFor="minp">
            Min net profit (£)
          </label>
          <input id="minp" type="number" min={0} step={5} className="input" value={params.min_profit} onChange={(e) => set("min_profit", Number(e.target.value))} />
        </div>
        <div className="lg:col-span-2">
          <label className="label" htmlFor="minr">
            Min ROI (%)
          </label>
          <input id="minr" type="number" min={0} step={5} className="input" value={params.min_roi} onChange={(e) => set("min_roi", Number(e.target.value))} />
        </div>
        <div className="lg:col-span-4">
          <span className="label">Sources</span>
          <div className="flex flex-wrap gap-3 pt-1.5">
            {SOURCES.map((s) => (
              <label key={s.id} className="flex cursor-pointer items-center gap-1.5 text-sm">
                <input type="checkbox" className="accent-emerald-600" checked={params.sources.includes(s.id)} onChange={() => toggleSource(s.id)} />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        <div className="lg:col-span-4">
          <span className="label">Options</span>
          <div className="flex flex-wrap gap-3 pt-1.5 text-sm">
            <label className="flex cursor-pointer items-center gap-1.5" title="Show spares/repairs, box only, iCloud locked etc.">
              <input type="checkbox" className="accent-emerald-600" checked={params.include_flagged} onChange={(e) => set("include_flagged", e.target.checked)} />
              Show red-flag items
            </label>
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                className="accent-emerald-600"
                checked={params.include_below_threshold}
                onChange={(e) => set("include_below_threshold", e.target.checked)}
              />
              Show below threshold
            </label>
            <label className="flex cursor-pointer items-center gap-1.5" title="Use labelled fixture data instead of live marketplaces">
              <input type="checkbox" className="accent-amber-500" checked={params.demo} onChange={(e) => set("demo", e.target.checked)} />
              Demo data
            </label>
          </div>
        </div>
      </div>
    </form>
  );
}
