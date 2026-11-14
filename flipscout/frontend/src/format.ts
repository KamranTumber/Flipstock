export const gbp = (n: number | null | undefined, dp = 2) =>
  n == null ? "—" : (n < 0 ? "−£" : "£") + Math.abs(n).toLocaleString("en-GB", { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const gbp0 = (n: number | null | undefined) => gbp(n, 0);

export const pct = (n: number | null | undefined) => (n == null ? "—" : `${n.toFixed(0)}%`);

export const miles = (n: number | null | undefined) => (n == null ? "? mi" : n < 10 ? `${n.toFixed(1)} mi` : `${Math.round(n)} mi`);

export const SOURCE_META: Record<string, { label: string; cls: string }> = {
  ebay: { label: "eBay", cls: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300" },
  gumtree: { label: "Gumtree", cls: "bg-lime-100 text-lime-800 dark:bg-lime-500/15 dark:text-lime-300" },
  facebook: { label: "FB", cls: "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-300" },
  cex: { label: "CeX", cls: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300" },
};

export const EXIT_LABEL: Record<string, string> = { ebay: "eBay", facebook: "FB", cex: "CeX" };

export const profitTone = (n: number | null | undefined) =>
  n == null || n === 0 ? "text-slate-500 dark:text-slate-400" : n > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400";
