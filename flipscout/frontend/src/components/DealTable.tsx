import { Bookmark, BookmarkCheck, ExternalLink, ListTree } from "lucide-react";
import type { Deal } from "../types";
import { EXIT_LABEL, gbp0, miles, pct, profitTone } from "../format";
import { SourceBadge } from "./DealCard";

interface Props {
  deals: Deal[];
  watched: Set<string>;
  onWatch: (d: Deal) => void;
  onDetails: (d: Deal) => void;
}

export default function DealTable({ deals, watched, onWatch, onDetails }: Props) {
  const exit = (d: Deal, ch: string) => d.exits.find((e) => e.channel === ch);
  return (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
          <tr>
            <th className="p-2">Item</th>
            <th className="p-2 text-right">Dist.</th>
            <th className="p-2 text-right">Buy (all-in)</th>
            <th className="p-2 text-right">eBay net</th>
            <th className="p-2 text-right">FB net</th>
            <th className="p-2 text-right">CeX net</th>
            <th className="p-2 text-right">Best</th>
            <th className="p-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {deals.map((d) => (
            <tr key={d.listing.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/60">
              <td className="max-w-sm p-2">
                <div className="flex items-center gap-2">
                  <SourceBadge source={d.listing.source} demo={d.listing.is_demo} />
                  <span className="truncate" title={d.listing.title}>
                    {d.listing.title}
                  </span>
                </div>
              </td>
              <td className="tabular p-2 text-right text-slate-500">{miles(d.listing.distance_miles)}</td>
              <td className="tabular p-2 text-right">{gbp0(d.buy_cost.total)}</td>
              {["ebay", "facebook", "cex"].map((ch) => {
                const e = exit(d, ch);
                return (
                  <td key={ch} className={`tabular p-2 text-right ${profitTone(e?.available ? e.profit : null)}`}>
                    {e?.available ? gbp0(e.profit) : "—"}
                  </td>
                );
              })}
              <td className="tabular p-2 text-right font-semibold">
                <span className={profitTone(d.best_profit)}>{gbp0(d.best_profit)}</span>
                <div className="text-[11px] font-normal text-slate-500">
                  {d.best_exit ? EXIT_LABEL[d.best_exit] : ""} {pct(d.best_roi)}
                </div>
              </td>
              <td className="whitespace-nowrap p-2 text-right">
                <a className="btn-ghost p-1" href={d.listing.url} target="_blank" rel="noopener noreferrer" title="Buy now">
                  <ExternalLink className="h-4 w-4" />
                </a>
                <button className="btn-ghost p-1" onClick={() => onDetails(d)} title="Breakdown">
                  <ListTree className="h-4 w-4" />
                </button>
                <button className="btn-ghost p-1" onClick={() => onWatch(d)} title="Save">
                  {watched.has(d.listing.id) ? <BookmarkCheck className="h-4 w-4 text-emerald-500" /> : <Bookmark className="h-4 w-4" />}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
