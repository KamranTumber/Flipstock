# FlipScout UK

A local-first electronics arbitrage tool for the UK. Give it a search term (or a preset category) and your postcode. It then:

1. **Sources** listings from **eBay UK**, **Gumtree** and **Facebook Marketplace** in parallel.
2. **Values** each item against **eBay UK sold prices** (median), **CeX** cash/voucher trade-in offers and **local FB Marketplace** prices.
3. **Itemises** the profit for each exit route: purchase price, inbound postage or round-trip fuel, eBay fees, promoted-listing fees and tiered outbound postage.
4. Picks the **best exit**, e.g. *"Best: £65 net on eBay"* or *"Risk-free: £40 instant cash at CeX"*.

Results, sold comps, CeX boxes and geocodes are cached in SQLite, so repeat searches come back instantly.

---

## Quick start

**Requirements:** Python 3.11+ and Node 18+. [`uv`](https://docs.astral.sh/uv/) is used if installed, otherwise `venv` + `pip`.

**macOS / Linux / Git Bash**
```bash
./start.sh            # dev mode → http://localhost:5173
./start.sh --prod     # single server → http://localhost:8000
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1          # → http://localhost:5173
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Prod    # → http://localhost:8000
```

On first run the script:
- creates `.env` from `.env.example`
- creates `backend/.venv` and installs `requirements.txt`
- runs `playwright install chromium` (about 150 MB, only needed for Facebook)
- runs `npm install`

It then starts uvicorn on `:8000` and Vite on `:5173`. Vite proxies `/api` to the backend.

> Want to look around without hitting any marketplace? Tick **Demo data** in the search panel, or set `DEMO_MODE=true`. Every demo item is badged **DEMO DATA**.

### Connecting the eBay API (recommended)
eBay usually refuses automated requests to its search pages (HTTP 403), so live eBay listings need the free official API:

1. Sign in at [developer.ebay.com](https://developer.ebay.com) with your eBay account and join the Developers Program (free).
2. Open **Application Keys** and create a **Production** keyset. Sandbox keys (containing `SBX`) only see fake test data.
3. eBay may ask about **Marketplace Account Deletion** notifications before the Production keys are enabled. FlipScout doesn't store eBay users' personal data, so you can choose the option to **opt out / apply for an exemption** for that reason.
4. Copy the **App ID (Client ID)** and **Cert ID (Client Secret)**, and paste them into **Settings → eBay API keys** (or into `.env` as `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`).
5. Click **Save settings**, then **Test connection**. It should report live UK listings.

### Manual setup
```bash
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev
```

### Tests
```bash
cd backend
python -m pytest -q
```
The suite covers:
- the profit calculator
- the rapidfuzz title normaliser, matcher and red-flag filter
- the HTML/JSON parsers for each marketplace
- an end-to-end API run in demo mode (including the SSE stream, watchlist CRUD and settings masking)

---

## Data sources & what to expect

| Source | Used for | How | Notes |
|---|---|---|---|
| **postcodes.io** | Postcode → lat/lng, outcode, district; town → lat/lng for distances | Free REST API | No key needed |
| **eBay UK** | Active BIN and ending-soon auctions | **Official Browse API** if `EBAY_CLIENT_ID/SECRET` are set, otherwise the public search page (`LH_PrefLoc=1`, `_stpos=<postcode>`) | eBay often answers automated page requests with **HTTP 403**. You'll see a *Blocked* badge if so. Free keys from [developer.ebay.com](https://developer.ebay.com) fix active search. |
| **eBay UK sold** | Median sold price, average postage, sample size | Public `LH_Sold=1&LH_Complete=1` page | If the sold page is refused and API keys are set, the app falls back to an estimate of active BIN prices × 0.9. This is labelled *active (estimate)* and marked high risk. eBay's sold-data API (Marketplace Insights) is restricted access. |
| **Gumtree** | Local classifieds by postcode + radius | Server-rendered search page, parsed via stable `data-q` attributes | Worked with plain HTTP when this was built |
| **Facebook Marketplace** | Local listings and local comps | Headless Chromium (Playwright) with **your own** `c_user` / `xs` cookies | Without cookies FB usually shows a login wall. The UI then shows *"FB Marketplace: Login cookie required — showing eBay & Gumtree results"*. Set `FB_FALLBACK=demo` to fill the gap with labelled demo items. |
| **CeX** | Cash and voucher trade-in prices, plus CeX's own selling price as a ceiling | The public Algolia search index that uk.webuy.com itself uses | The search-only key lives in `.env` in case CeX rotates it |

All scrapers share a few safeguards:
- a per-host rate limit with jitter (`MIN_REQUEST_INTERVAL`)
- rotating User-Agents
- retry with back-off on 429/503
- block / CAPTCHA / login-wall detection

A source that fails becomes a **status badge**, never a crashed search. The other sources' results are still shown.

> Scraping terms differ per site. Use this for personal research at a polite request rate. The eBay Browse API is the supported route for eBay.

---

## How valuation works

**Normalising titles** (`services/normalizer.py`)
- Fluff words are stripped: RARE, MINT, L@@K, BUNDLE, boxed, …
- Product aliases are unified: "PlayStation 5" → `ps5`, "RTX 3080" → `rtx3080`, "128 GB" → `128gb`.

**Red flags.** These titles are flagged and hidden by default (toggle **Show red-flag items** to see them):
- spares/repairs, faulty, box only, read description
- iCloud/activation locked, blacklisted
- broken/cracked, untested, replica, wanted ads

Descriptions are also checked for the most serious of these.

**Matching.** The score is a blend of rapidfuzz `token_set_ratio` and `token_sort_ratio`, with hard penalties for:
- **Model-number mismatch** (3080 vs 3070, iPhone 13 vs 14) → capped at 35
- **Variant mismatch** (Pro / Max / Mini / Ti / Super / Slim / Digital / OLED …) → −14 each
- **Storage mismatch** (128GB vs 512GB) → −18
- **Accessory vs device** ("PS5 DualSense Controller" vs "PS5 Console") → capped at 30. Inclusions such as "with 2 controllers" are understood.
- **Spares vs working** → capped at 25

A comp only counts if it scores ≥ `MATCH_THRESHOLD` (default 72).

**eBay sold value** (`services/comps.py`)
- Only matched sold items count, excluding "for parts".
- Same-condition comps are preferred (new vs used) when there are at least 3.
- Outliers are trimmed with IQR, then the **median** is taken.

**FB local value**
- If at least 3 matching active local FB listings exist: their median × haggle discount (0.92).
- Otherwise: eBay median × `fb_local_factor` (0.90), labelled *estimate*.

**CeX** uses the best-matching box. Boxes CeX will actually buy are preferred.

**Pooling.** Comps are pooled per search query. Listings whose pool is thin trigger up to `MAX_COMP_LOOKUPS` extra targeted sold and CeX searches, all cached.

## Profit maths (`services/profit.py`)

```
Buy cost   = price + inbound postage                         (posted items)
           = price + miles × 2 × fuel p/mi ÷ 100             (collection items)

eBay exit  = sold median − fees − promoted % − outbound postage tier
             fees: private 0% (default) | business 12.8% + £0.30 (configurable)
             postage: small £3.50 · medium (GPU/console) £6.50 · insured £11.00 when sale ≥ £250
FB exit    = local cash value − £0 fees − £0 postage
CeX exit   = cash (or voucher) offer − optional drop-off fuel

Profit = exit net − buy cost      ROI = profit ÷ buy cost × 100
```

Every deal card shows the three exits side by side. **Breakdown** opens a drawer with every line item, the matched sold comps (with match scores), the CeX box and the FB estimate method.

---

## Using the app

- **Search panel:** query or preset, postcode, radius (5 / 10 / 25 / 50 miles or nationwide), min net profit, min ROI, source toggles, red-flag / below-threshold / demo toggles.
- **Live progress:** the search streams over Server-Sent Events (`/api/search/stream`), so each source's badge updates as it finishes.
- **Deal feed:** grid or table view, sortable by net profit, ROI, distance or newly listed. Each card has **Buy now**, **View comps**, **Breakdown** and **Save** buttons.
- **Saved flips:** track deals as `Watching → Purchased → Listed → Sold`, with notes and actual buy/sale prices for realised profit.
- **Settings:** fuel p/mile, postage tiers, eBay private/business fee preset, promoted %, FB factors, CeX cash/voucher and drop-off miles, default search values, and FB cookies (stored only in your local SQLite and masked in the UI).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Config status (demo mode, eBay API, FB cookies) |
| GET | `/api/presets` | Preset categories and their queries |
| GET | `/api/geocode?postcode=` | postcodes.io lookup |
| POST | `/api/search` | Full search (JSON `SearchRequest`) |
| GET | `/api/search/stream?…` | Same search, as SSE progress events plus a final `result` |
| GET/PUT | `/api/settings` | User settings |
| GET/POST | `/api/watchlist` | List / save a deal |
| PATCH/DELETE | `/api/watchlist/{id}` | Update status, notes and prices / remove |

Interactive docs: http://localhost:8000/docs

## Project layout

```
backend/
  app/
    main.py              FastAPI routes, SSE stream, serves frontend/dist in --prod
    config.py            .env settings (pydantic-settings)
    db.py, models.py     SQLite via SQLModel: cache, geocodes, sold price history, watchlist, settings
    schemas.py           Pydantic models shared by scrapers, services and API
    scrapers/
      base.py            HTTP client, UA rotation, per-host rate limiter, retries, block detection
      browser.py         Shared Playwright Chromium pool
      ebay.py            Browse API + search/sold HTML parser (s-item and s-card layouts)
      gumtree.py         Gumtree search parser
      cex.py             CeX Algolia client
      facebook.py        FB Marketplace (Playwright + cookies) + pure HTML parser
      demo.py            Labelled deterministic demo data
    services/
      geocode.py         postcodes.io + haversine
      normalizer.py      Fluff stripping, red flags, rapidfuzz matching, categories
      comps.py           eBay median / CeX best match / FB local valuation
      profit.py          Pure profit & cost-breakdown engine
      search.py          Orchestrator (asyncio.gather across sources and comps)
      cache.py           SQLite JSON cache
      user_settings.py   Settings persistence and cookie masking
  tests/                 pytest suite
frontend/                Vite + React + TypeScript + Tailwind v4 + lucide-react
start.sh / start.ps1     One-command boot
```

## Troubleshooting

- **eBay badge says "Blocked" (HTTP 403):** add your eBay API keys in Settings (see *Connecting the eBay API*).
- **Test connection says "client authentication failed":** the keys are wrong or are Sandbox keys. Use the Production App ID and Cert ID.
- **FB badge says "Login cookie required":** paste `c_user` and `xs` into Settings. If it says the cookies were rejected, they've expired, so copy them again.
- **FB badge says "unavailable":** run `python -m playwright install chromium` inside `backend/.venv`.
- **CeX badge shows an error:** CeX may have rotated its public search key. Copy the new `x-algolia-api-key` from the network tab on uk.webuy.com into `.env`.
- **Clear the cache:** delete `data/flipscout.db`. Your watchlist and settings live there too.
