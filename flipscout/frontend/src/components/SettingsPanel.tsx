import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, PlugZap, Save, XCircle } from "lucide-react";
import { api } from "../api";
import type { EbayTestResult, Health, UserSettings } from "../types";

interface Props {
  settings: UserSettings | null;
  health: Health | null;
  onSave: (s: UserSettings) => Promise<void>;
}

function Num({ label, value, onChange, step = 0.5, suffix }: { label: string; value: number; onChange: (n: number) => void; step?: number; suffix?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <div className="relative">
        <input type="number" step={step} className="input pr-10" value={value} onChange={(e) => onChange(Number(e.target.value))} />
        {suffix && <span className="pointer-events-none absolute right-3 top-2 text-sm text-slate-400">{suffix}</span>}
      </div>
    </label>
  );
}

export default function SettingsPanel({ settings, health, onSave }: Props) {
  const [s, setS] = useState<UserSettings | null>(settings);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<EbayTestResult | null>(null);
  useEffect(() => setS(settings), [settings]);
  if (!s) return <div className="card p-6 text-sm text-slate-500">Loading settings…</div>;
  const set = <K extends keyof UserSettings>(k: K, v: UserSettings[K]) => {
    setSaved(false);
    setS({ ...s, [k]: v });
  };

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
          await onSave(s);
          setSaved(true);
        } finally {
          setSaving(false);
        }
      }}
    >
      <section className="card p-4">
        <h3 className="mb-3 font-semibold">Search defaults</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="label">Default postcode</span>
            <input className="input uppercase" value={s.default_postcode} onChange={(e) => set("default_postcode", e.target.value.toUpperCase())} />
          </label>
          <Num label="Default radius" value={s.default_radius} step={5} suffix="mi" onChange={(v) => set("default_radius", v)} />
          <Num label="Default min profit" value={s.default_min_profit} step={5} suffix="£" onChange={(v) => set("default_min_profit", v)} />
          <Num label="Default min ROI" value={s.default_min_roi} step={5} suffix="%" onChange={(v) => set("default_min_roi", v)} />
        </div>
      </section>

      <section className="card p-4">
        <h3 className="mb-3 font-semibold">Travel & postage</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Num label="Fuel cost" value={s.fuel_pence_per_mile} suffix="p/mi" onChange={(v) => set("fuel_pence_per_mile", v)} />
          <Num label="Small parcel" value={s.ship_small} step={0.1} suffix="£" onChange={(v) => set("ship_small", v)} />
          <Num label="Medium (GPU/console)" value={s.ship_medium} step={0.1} suffix="£" onChange={(v) => set("ship_medium", v)} />
          <Num label="Insured high value" value={s.ship_high_value} step={0.1} suffix="£" onChange={(v) => set("ship_high_value", v)} />
          <Num label="High value from" value={s.high_value_threshold} step={10} suffix="£" onChange={(v) => set("high_value_threshold", v)} />
        </div>
        <p className="mt-2 text-xs text-slate-500">Fuel is charged on the round trip for collection-only listings (Gumtree / FB / eBay collection).</p>
      </section>

      <section className="card p-4">
        <h3 className="mb-3 font-semibold">eBay selling fees</h3>
        <div className="mb-3 flex gap-2">
          {(["private", "business"] as const).map((t) => (
            <button
              type="button"
              key={t}
              onClick={() => set("ebay_seller_type", t)}
              className={`rounded-lg border px-3 py-1.5 text-sm capitalize ${s.ebay_seller_type === t ? "border-emerald-500 bg-emerald-50 font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" : "border-slate-300 dark:border-slate-700"}`}
            >
              {t === "private" ? "Private seller (0%)" : "Business account"}
            </button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {s.ebay_seller_type === "business" ? (
            <>
              <Num label="Final value fee" value={s.ebay_business_fee_pct} step={0.1} suffix="%" onChange={(v) => set("ebay_business_fee_pct", v)} />
              <Num label="Per-order fee" value={s.ebay_business_fixed_fee} step={0.05} suffix="£" onChange={(v) => set("ebay_business_fixed_fee", v)} />
            </>
          ) : (
            <Num label="Private seller fee" value={s.ebay_private_fee_pct} step={0.1} suffix="%" onChange={(v) => set("ebay_private_fee_pct", v)} />
          )}
          <Num label="Promoted listing" value={s.ebay_promoted_pct} step={0.5} suffix="%" onChange={(v) => set("ebay_promoted_pct", v)} />
        </div>
      </section>

      <section className="card p-4">
        <h3 className="mb-3 font-semibold">FB Marketplace & CeX</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Num label="FB value vs eBay median" value={s.fb_local_factor} step={0.01} suffix="×" onChange={(v) => set("fb_local_factor", v)} />
          <Num label="FB haggle discount" value={s.fb_active_discount} step={0.01} suffix="×" onChange={(v) => set("fb_active_discount", v)} />
          <label className="block">
            <span className="label">CeX payout</span>
            <select className="input" value={s.cex_payout} onChange={(e) => set("cex_payout", e.target.value as "cash" | "voucher")}>
              <option value="cash">Cash</option>
              <option value="voucher">Voucher</option>
            </select>
          </label>
          <Num label="Miles to nearest CeX" value={s.cex_dropoff_miles} step={1} suffix="mi" onChange={(v) => set("cex_dropoff_miles", v)} />
        </div>
      </section>

      <section className="card p-4">
        <h3 className="mb-1 font-semibold">eBay API keys</h3>
        <p className="mb-3 text-xs text-slate-500">
          Free from{" "}
          <a className="text-emerald-700 underline dark:text-emerald-400" href="https://developer.ebay.com/my/keys" target="_blank" rel="noopener noreferrer">
            developer.ebay.com → Application Keys
          </a>
          . Use the <b>Production</b> keyset: App ID (Client ID) and Cert ID (Client Secret). Stored only in your local SQLite database. Save, then test.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">App ID (Client ID)</span>
            <input className="input font-mono" autoComplete="off" spellCheck={false} placeholder="YourName-FlipScou-PRD-…" value={s.ebay_client_id} onChange={(e) => set("ebay_client_id", e.target.value)} />
          </label>
          <label className="block">
            <span className="label">Cert ID (Client Secret)</span>
            <input className="input font-mono" type="password" autoComplete="off" placeholder="PRD-…" value={s.ebay_client_secret} onChange={(e) => set("ebay_client_secret", e.target.value)} />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-ghost border border-slate-300 dark:border-slate-700"
            disabled={testing || !s.ebay_api_configured}
            title={s.ebay_api_configured ? "" : "Save keys first"}
            onClick={async () => {
              setTesting(true);
              setTest(null);
              try {
                setTest(await api.testEbay());
              } catch (e) {
                setTest({ ok: false, message: String(e) });
              } finally {
                setTesting(false);
              }
            }}
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />} Test connection
          </button>
          {test && (
            <span className={`inline-flex items-center gap-1 text-sm ${test.ok ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
              {test.ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />} {test.message}
            </span>
          )}
        </div>
        {test?.sample && test.sample.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-slate-500">
            {test.sample.map((x) => (
              <li key={x.url} className="truncate">
                £{x.price.toFixed(2)} · {x.title}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card p-4">
        <h3 className="mb-1 font-semibold">Facebook cookies</h3>
        <p className="mb-3 text-xs text-slate-500">
          Optional. From your own logged-in browser (DevTools → Application → Cookies → facebook.com). Stored only in your local SQLite database.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="label">FB c_user</span>
            <input className="input font-mono" autoComplete="off" value={s.fb_c_user} onChange={(e) => set("fb_c_user", e.target.value)} />
          </label>
          <label className="block">
            <span className="label">FB xs</span>
            <input className="input font-mono" type="password" autoComplete="off" value={s.fb_xs} onChange={(e) => set("fb_xs", e.target.value)} />
          </label>
        </div>
        <ul className="mt-3 flex flex-wrap gap-3 text-xs">
          <li>FB cookies: <b>{s.fb_cookie_configured ? "configured" : "not set"}</b></li>
          <li>eBay Browse API: <b>{s.ebay_api_configured ? "configured" : "not set (HTML fallback)"}</b></li>
          <li>Demo mode (.env): <b>{health?.demo_mode ? "on" : "off"}</b></li>
        </ul>
      </section>

      <div className="flex items-center gap-3">
        <button className="btn-primary" disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save settings
        </button>
        {saved && (
          <span className="inline-flex items-center gap-1 text-sm text-emerald-600">
            <CheckCircle2 className="h-4 w-4" /> Saved — applies to your next search
          </span>
        )}
      </div>
    </form>
  );
}
