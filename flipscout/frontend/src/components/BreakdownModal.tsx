import { useEffect } from "react";
import { ExternalLink, X } from "lucide-react";
import type { CostLine, Deal, ExitChannel } from "../types";
import { gbp, pct, profitTone } from "../format";
import { SourceBadge } from "./DealCard";

function Lines({ lines }: { lines: CostLine[] }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {lines.map((l, i) => (
          <tr key={i} className="border-b border-dashed border-slate-200 last:border-0 dark:border-slate-800">
            <td className="py-1 pr-2 text-slate-600 dark:text-slate-300">{l.label}</td>
            <td className={`tabular py-1 text-right ${l.amount < 0 ? "text-rose-600 dark:text-rose-400" : l.amount > 0 ? "" : "text-slate-400"}`}>
              {l.amount > 0 ? "+" : ""}
              {gbp(l.amount)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const RISK_CLS = {
  low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  high: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
};

function ExitBlock({ e, buyTotal, best }: { e: ExitChannel; buyTotal: number; best: boolean }) {
  return (
    <section className={`rounded-xl border p-3 ${best ? "border-emerald-400 dark:border-emerald-500/50" : "border-slate-200 dark:border-slate-800"}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="font-semibold">
          {e.label} {best && <span className="ml-1 rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">Best</span>}
        </h4>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${RISK_CLS[e.risk]}`}>{e.risk} risk</span>
      </div>
      {e.available ? (
        <>
          <Lines lines={e.lines} />
          <div className="mt-2 space-y-0.5 border-t border-slate-200 pt-2 text-sm dark:border-slate-800">
            <div className="flex justify-between">
              <span>Net proceeds</span>
              <span className="tabular font-medium">{gbp(e.net_proceeds)}</span>
            </div>
            <div className="flex justify-between text-slate-500 dark:text-slate-400">
              <span>− Total buy cost</span>
              <span className="tabular">{gbp(buyTotal)}</span>
            </div>
            <div className={`flex justify-between text-base font-bold ${profitTone(e.profit)}`}>
              <span>= Net profit · ROI {pct(e.roi)}</span>
              <span className="tabular">{gbp(e.profit)}</span>
            </div>
          </div>
          {e.note && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{e.note}</p>}
          {e.link && (
            <a href={e.link} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-emerald-700 hover:underline dark:text-emerald-400">
              Open source <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-500">{e.note}</p>
      )}
    </section>
  );
}

export default function BreakdownModal({ deal, onClose }: { deal: Deal; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  const l = deal.listing;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/50 backdrop-blur-sm" onClick={onClose} role="dialog" aria-modal="true">
      <div className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-2xl dark:bg-slate-950" onClick={(e) => e.stopPropagation()}>
        <header className="sticky top-0 z-10 flex items-start gap-3 border-b border-slate-200 bg-white/95 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
          <div className="min-w-0 flex-1">
            <SourceBadge source={l.source} demo={l.is_demo} />
            <h2 className="mt-1 text-lg font-semibold leading-snug">{l.title}</h2>
            <p className="text-xs text-slate-500">
              Matched as “{deal.normalized_title}” · category: {deal.category}
            </p>
          </div>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="space-y-4 p-4">
          {deal.flags.length > 0 && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              <b>Red flags:</b> {deal.flags.join(", ")}. Valuations assume a working, complete item — treat with caution.
            </div>
          )}

          <section className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
            <h4 className="mb-2 font-semibold">Buy cost</h4>
            <Lines lines={deal.buy_cost.lines} />
            <div className="mt-2 flex justify-between border-t border-slate-200 pt-2 font-bold dark:border-slate-800">
              <span>Total buy cost</span>
              <span className="tabular">{gbp(deal.buy_cost.total)}</span>
            </div>
          </section>

          {deal.exits.map((e) => (
            <ExitBlock key={e.channel} e={e} buyTotal={deal.buy_cost.total} best={deal.best_exit === e.channel} />
          ))}

          {deal.ebay && (
            <section className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="font-semibold">
                  eBay {deal.ebay.method === "sold" ? "sold" : "active (estimate)"} comps · {deal.ebay.sample_size} matched
                </h4>
                <a href={deal.ebay.comps_url} target="_blank" rel="noopener noreferrer" className="text-xs text-emerald-700 hover:underline dark:text-emerald-400">
                  View all on eBay
                </a>
              </div>
              <div className="mb-2 grid grid-cols-4 gap-2 text-center text-xs">
                {[
                  ["Median", deal.ebay.median],
                  ["Mean", deal.ebay.mean],
                  ["Low", deal.ebay.low],
                  ["High", deal.ebay.high],
                ].map(([k, v]) => (
                  <div key={k as string} className="rounded-lg bg-slate-100 p-1.5 dark:bg-slate-900">
                    <div className="text-slate-500">{k}</div>
                    <div className="tabular font-semibold">{gbp(v as number)}</div>
                  </div>
                ))}
              </div>
              {deal.ebay.avg_shipping != null && <p className="mb-1 text-xs text-slate-500">Average buyer postage on comps: {gbp(deal.ebay.avg_shipping)}</p>}
              <ul className="divide-y divide-slate-200 text-xs dark:divide-slate-800">
                {deal.ebay.comps.map((c) => (
                  <li key={c.url} className="flex items-center gap-2 py-1.5">
                    <a href={c.url} target="_blank" rel="noopener noreferrer" className="min-w-0 flex-1 truncate hover:underline" title={c.title}>
                      {c.title}
                    </a>
                    <span className="shrink-0 text-slate-500">{c.sold_date ?? c.condition ?? ""}</span>
                    <span className="shrink-0 rounded bg-slate-100 px-1 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300" title="rapidfuzz match score">
                      {c.match_score?.toFixed(0)}
                    </span>
                    <span className="tabular w-16 shrink-0 text-right font-medium">{gbp(c.price)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {deal.cex && (
            <section className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <h4 className="mb-1 font-semibold">CeX match</h4>
              <a href={deal.cex.url} target="_blank" rel="noopener noreferrer" className="text-sm hover:underline">
                {deal.cex.name}
              </a>
              <span className="ml-2 text-xs text-slate-500">match {deal.cex.match_score?.toFixed(0)}</span>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                {[
                  ["Cash", deal.cex.cash],
                  ["Voucher", deal.cex.voucher],
                  ["CeX sells at", deal.cex.retail],
                ].map(([k, v]) => (
                  <div key={k as string} className="rounded-lg bg-slate-100 p-1.5 dark:bg-slate-900">
                    <div className="text-slate-500">{k}</div>
                    <div className="tabular font-semibold">{gbp(v as number | null)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {deal.fb && (
            <section className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800">
              <h4 className="mb-1 font-semibold">FB Marketplace local value</h4>
              <p>
                <span className="tabular font-semibold">{gbp(deal.fb.value)}</span> — {deal.fb.note}
              </p>
            </section>
          )}

          {l.description && (
            <section className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800">
              <h4 className="mb-1 font-semibold">Listing description (excerpt)</h4>
              <p className="whitespace-pre-line text-slate-600 dark:text-slate-300">{l.description}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
