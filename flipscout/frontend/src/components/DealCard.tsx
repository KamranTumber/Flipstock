import { AlertTriangle, Bookmark, BookmarkCheck, ExternalLink, Gavel, ImageOff, ListTree, MapPin, ShieldCheck, Trophy, Truck } from "lucide-react";
import type { Deal, ExitChannel } from "../types";
import { EXIT_LABEL, SOURCE_META, gbp, gbp0, miles, pct, profitTone } from "../format";

export function SourceBadge({ source, demo }: { source: string; demo?: boolean }) {
  const m = SOURCE_META[source] ?? { label: source, cls: "bg-slate-100 text-slate-700" };
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${m.cls}`}>{m.label}</span>
      {demo && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-800 dark:bg-amber-500/20 dark:text-amber-300">Demo data</span>}
    </span>
  );
}

function ExitCell({ e, best }: { e: ExitChannel; best: boolean }) {
  return (
    <div
      className={`rounded-lg border p-2 text-center ${
        best ? "border-emerald-400 bg-emerald-50/70 dark:border-emerald-500/50 dark:bg-emerald-500/10" : "border-slate-200 dark:border-slate-800"
      }`}
      title={e.note}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{EXIT_LABEL[e.channel]}</div>
      {e.available ? (
        <>
          <div className="tabular text-[11px] text-slate-500 dark:text-slate-400">sells {gbp0(e.sale_price)}</div>
          <div className={`tabular text-base font-bold ${profitTone(e.profit)}`}>{gbp0(e.profit)}</div>
          <div className="tabular text-[11px] text-slate-500 dark:text-slate-400">ROI {pct(e.roi)}</div>
        </>
      ) : (
        <div className="py-2 text-xs text-slate-400">no match</div>
      )}
    </div>
  );
}

interface Props {
  deal: Deal;
  watched: boolean;
  onWatch: (d: Deal) => void;
  onDetails: (d: Deal) => void;
}

export default function DealCard({ deal, watched, onWatch, onDetails }: Props) {
  const l = deal.listing;
  return (
    <article className="card flex flex-col overflow-hidden">
      <div className="flex gap-3 p-3">
        <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
          {l.image_url ? (
            <img src={l.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-slate-400">
              <ImageOff className="h-6 w-6" />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            <SourceBadge source={l.source} demo={l.is_demo} />
            {l.listing_type === "auction" && (
              <span className="inline-flex items-center gap-1 rounded bg-purple-100 px-1.5 py-0.5 text-[11px] font-medium text-purple-800 dark:bg-purple-500/15 dark:text-purple-300">
                <Gavel className="h-3 w-3" /> Auction{l.bids != null ? ` · ${l.bids} bids` : ""}
              </span>
            )}
            <span className="inline-flex items-center gap-0.5 text-[11px] text-slate-500 dark:text-slate-400">
              {l.is_collection ? <MapPin className="h-3 w-3" /> : <Truck className="h-3 w-3" />}
              {l.is_collection ? miles(l.distance_miles) : l.postage === 0 ? "Free postage" : l.postage != null ? `+${gbp(l.postage)} post` : "Postage ?"}
              {!l.is_collection && l.distance_miles != null && ` · ${miles(l.distance_miles)}`}
            </span>
          </div>
          <h3 className="line-clamp-2 text-sm font-semibold leading-snug" title={l.title}>
            {l.title}
          </h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="tabular text-lg font-bold">{gbp(l.price)}</span>
            <span className="tabular text-xs text-slate-500 dark:text-slate-400">all-in {gbp(deal.buy_cost.total)}</span>
          </div>
          <div className="truncate text-[11px] text-slate-500 dark:text-slate-400">
            {[l.location, l.condition, l.time_left, l.posted_at].filter(Boolean).join(" · ")}
          </div>
        </div>
      </div>

      {(deal.badge || deal.risk_badge || deal.flags.length > 0) && (
        <div className="flex flex-wrap gap-1.5 px-3 pb-2">
          {deal.badge && (
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${(deal.best_profit ?? 0) > 0 ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300"}`}>
              <Trophy className="h-3 w-3" /> {deal.badge}
            </span>
          )}
          {deal.risk_badge && deal.best_exit !== "cex" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 ring-1 ring-red-200 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30">
              <ShieldCheck className="h-3 w-3" /> {deal.risk_badge}
            </span>
          )}
          {deal.flags.map((f) => (
            <span key={f} className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
              <AlertTriangle className="h-3 w-3" /> {f}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 px-3 pb-3">
        {deal.exits.map((e) => (
          <ExitCell key={e.channel} e={e} best={deal.best_exit === e.channel && (e.profit ?? 0) > 0} />
        ))}
      </div>

      <div className="mt-auto flex items-center gap-1 border-t border-slate-200 px-2 py-1.5 dark:border-slate-800">
        <a href={l.url} target="_blank" rel="noopener noreferrer" className="btn-ghost px-2 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
          <ExternalLink className="h-3.5 w-3.5" /> Buy now
        </a>
        {deal.ebay && (
          <a href={deal.ebay.comps_url} target="_blank" rel="noopener noreferrer" className="btn-ghost px-2 py-1 text-xs">
            View comps
          </a>
        )}
        <button className="btn-ghost px-2 py-1 text-xs" onClick={() => onDetails(deal)}>
          <ListTree className="h-3.5 w-3.5" /> Breakdown
        </button>
        <button
          className={`btn-ghost ml-auto px-2 py-1 text-xs ${watched ? "text-emerald-600 dark:text-emerald-400" : ""}`}
          onClick={() => onWatch(deal)}
          title={watched ? "Saved to watchlist" : "Save to watchlist"}
        >
          {watched ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
        </button>
      </div>
    </article>
  );
}
