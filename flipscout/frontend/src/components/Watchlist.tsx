import { useState } from "react";
import { ExternalLink, ListTree, Trash2 } from "lucide-react";
import type { Deal, WatchlistItem, WatchStatus } from "../types";
import { EXIT_LABEL, gbp, profitTone } from "../format";
import { SourceBadge } from "./DealCard";

const STATUSES: WatchStatus[] = ["watching", "purchased", "listed", "sold"];
const STATUS_CLS: Record<WatchStatus, string> = {
  watching: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  purchased: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
  listed: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  sold: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

interface Props {
  items: WatchlistItem[];
  onUpdate: (id: number, patch: Partial<WatchlistItem>) => void;
  onDelete: (id: number) => void;
  onDetails: (d: Deal) => void;
}

function NumberCell({ value, onSave, placeholder }: { value: number | null; onSave: (v: number | null) => void; placeholder: string }) {
  const [v, setV] = useState(value?.toString() ?? "");
  return (
    <input
      className="input w-24 px-2 py-1 text-xs"
      inputMode="decimal"
      placeholder={placeholder}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        const n = v.trim() === "" ? null : Number(v);
        if (n !== value && (n === null || !Number.isNaN(n))) onSave(n);
      }}
    />
  );
}

export default function Watchlist({ items, onUpdate, onDelete, onDetails }: Props) {
  const [filter, setFilter] = useState<WatchStatus | "all">("all");
  const shown = filter === "all" ? items : items.filter((i) => i.status === filter);
  const realised = items.reduce((a, i) => a + (i.realised_profit ?? 0), 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {(["all", ...STATUSES] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${
              filter === s ? "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" : "border-slate-300 dark:border-slate-700"
            }`}
          >
            {s} ({s === "all" ? items.length : items.filter((i) => i.status === s).length})
          </button>
        ))}
        <span className="ml-auto text-sm">
          Realised profit: <b className={profitTone(realised)}>{gbp(realised)}</b>
        </span>
      </div>

      {shown.length === 0 ? (
        <div className="card p-8 text-center text-sm text-slate-500">No saved flips yet — bookmark a deal from the feed.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
              <tr>
                <th className="p-2">Item</th>
                <th className="p-2">Status</th>
                <th className="p-2 text-right">Listed at</th>
                <th className="p-2 text-right">Est. best</th>
                <th className="p-2">Paid</th>
                <th className="p-2">Sold for</th>
                <th className="p-2 text-right">Realised</th>
                <th className="p-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {shown.map((i) => (
                <tr key={i.id} className="align-top">
                  <td className="max-w-xs p-2">
                    <div className="flex items-center gap-1.5">
                      <SourceBadge source={i.source} demo={i.deal?.listing.is_demo} />
                    </div>
                    <a href={i.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium hover:underline">
                      {i.title}
                    </a>
                    <textarea
                      className="input mt-1 h-8 resize-y px-2 py-1 text-xs"
                      placeholder="Notes…"
                      defaultValue={i.notes}
                      onBlur={(e) => e.target.value !== i.notes && onUpdate(i.id, { notes: e.target.value })}
                    />
                  </td>
                  <td className="p-2">
                    <select
                      className={`rounded-md border-0 px-2 py-1 text-xs font-semibold capitalize ${STATUS_CLS[i.status]}`}
                      value={i.status}
                      onChange={(e) => onUpdate(i.id, { status: e.target.value as WatchStatus })}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="tabular p-2 text-right">{gbp(i.buy_price)}</td>
                  <td className={`tabular p-2 text-right ${profitTone(i.best_profit)}`}>
                    {gbp(i.best_profit)}
                    {i.best_channel && <div className="text-[11px] text-slate-500">{EXIT_LABEL[i.best_channel]}</div>}
                  </td>
                  <td className="p-2">
                    <NumberCell value={i.actual_buy_price} placeholder={i.buy_price.toFixed(0)} onSave={(v) => onUpdate(i.id, { actual_buy_price: v })} />
                  </td>
                  <td className="p-2">
                    <NumberCell value={i.actual_sale_price} placeholder="—" onSave={(v) => onUpdate(i.id, { actual_sale_price: v })} />
                  </td>
                  <td className={`tabular p-2 text-right font-semibold ${profitTone(i.realised_profit)}`}>{gbp(i.realised_profit)}</td>
                  <td className="whitespace-nowrap p-2 text-right">
                    {i.deal && (
                      <button className="btn-ghost p-1" title="Breakdown at time of saving" onClick={() => onDetails(i.deal!)}>
                        <ListTree className="h-4 w-4" />
                      </button>
                    )}
                    <a className="btn-ghost p-1" href={i.url} target="_blank" rel="noopener noreferrer" title="Open listing">
                      <ExternalLink className="h-4 w-4" />
                    </a>
                    <button className="btn-ghost p-1 text-rose-600" title="Remove" onClick={() => onDelete(i.id)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
