import { AlertTriangle, CheckCircle2, Database, FlaskConical, KeyRound, Loader2, ShieldAlert, XCircle } from "lucide-react";
import type { SourceStatus } from "../types";

const STYLE: Record<string, { cls: string; Icon: typeof CheckCircle2 }> = {
  ok: { cls: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300", Icon: CheckCircle2 },
  cached: { cls: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300", Icon: Database },
  demo: { cls: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300", Icon: FlaskConical },
  login_required: { cls: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/30 dark:bg-orange-500/10 dark:text-orange-300", Icon: KeyRound },
  blocked: { cls: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300", Icon: ShieldAlert },
  unavailable: { cls: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300", Icon: AlertTriangle },
  error: { cls: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300", Icon: XCircle },
  disabled: { cls: "border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400", Icon: AlertTriangle },
};

export default function StatusBar({ statuses }: { statuses: SourceStatus[] }) {
  if (!statuses.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {statuses.map((s) => {
        const st = STYLE[s.state] ?? STYLE.error;
        const Icon = s.pending ? Loader2 : st.Icon;
        const cls = s.pending ? "border-slate-300 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300" : st.cls;
        return (
          <div key={s.source} className={`flex max-w-full items-start gap-2 rounded-lg border px-3 py-1.5 text-xs ${cls}`} title={s.message}>
            <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${s.pending ? "animate-spin" : ""}`} />
            <span className="min-w-0">
              <span className="font-semibold">{s.label}:</span>{" "}
              <span className="break-words">{s.pending ? "searching…" : s.message}</span>
              {!s.pending && s.elapsed_ms > 0 && <span className="ml-1 opacity-60">({(s.elapsed_ms / 1000).toFixed(1)}s)</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
