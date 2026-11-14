export type SourceName = "ebay" | "gumtree" | "facebook";
export type ExitName = "ebay" | "facebook" | "cex";
export type SourceState = "ok" | "cached" | "blocked" | "login_required" | "error" | "unavailable" | "disabled" | "demo";

export interface GeoPoint {
  postcode: string;
  outcode: string;
  latitude: number;
  longitude: number;
  district?: string | null;
  region?: string | null;
}

export interface Listing {
  id: string;
  source: SourceName;
  title: string;
  price: number;
  postage: number | null;
  condition: string | null;
  listing_type: "buy_it_now" | "auction" | "classified";
  bids: number | null;
  time_left: string | null;
  seller_feedback: string | null;
  location: string | null;
  distance_miles: number | null;
  image_url: string | null;
  url: string;
  posted_at: string | null;
  description: string | null;
  is_collection: boolean;
  is_demo: boolean;
}

export interface SoldComp {
  title: string;
  price: number;
  shipping: number | null;
  condition: string | null;
  sold_date: string | null;
  url: string;
  match_score: number | null;
}

export interface CexBox {
  box_id: string;
  name: string;
  cash: number | null;
  voucher: number | null;
  retail: number | null;
  url: string;
  match_score: number | null;
}

export interface EbayValuation {
  median: number;
  mean: number;
  low: number;
  high: number;
  avg_shipping: number | null;
  sample_size: number;
  method: "sold" | "active_estimate";
  comps_url: string;
  comps: SoldComp[];
}

export interface FbValuation {
  value: number;
  method: "active_comps" | "heuristic";
  sample_size: number;
  note: string;
}

export interface CostLine {
  label: string;
  amount: number;
}

export interface ExitChannel {
  channel: ExitName;
  label: string;
  available: boolean;
  sale_price: number | null;
  lines: CostLine[];
  net_proceeds: number | null;
  profit: number | null;
  roi: number | null;
  risk: "low" | "medium" | "high";
  note: string;
  link: string | null;
}

export interface Deal {
  listing: Listing;
  normalized_title: string;
  category: string;
  flags: string[];
  buy_cost: { lines: CostLine[]; total: number };
  ebay: EbayValuation | null;
  cex: CexBox | null;
  fb: FbValuation | null;
  exits: ExitChannel[];
  best_exit: ExitName | null;
  best_profit: number | null;
  best_roi: number | null;
  risk_free_profit: number | null;
  badge: string | null;
  risk_badge: string | null;
  meets_threshold: boolean;
}

export interface SourceStatus {
  source: string;
  label: string;
  state: SourceState;
  message: string;
  count: number;
  elapsed_ms: number;
  pending?: boolean;
}

export interface SearchResponse {
  query: string;
  queries: string[];
  geo: GeoPoint;
  radius: number;
  deals: Deal[];
  statuses: SourceStatus[];
  total_listings: number;
  flagged_hidden: number;
  below_threshold_hidden: number;
  out_of_radius_hidden: number;
  elapsed_ms: number;
}

export interface SearchParams {
  q: string;
  preset: string;
  postcode: string;
  radius: number;
  min_profit: number;
  min_roi: number;
  sources: SourceName[];
  include_flagged: boolean;
  include_below_threshold: boolean;
  demo: boolean;
}

export interface Preset {
  id: string;
  label: string;
  queries: string[];
}

export interface UserSettings {
  default_postcode: string;
  default_radius: number;
  default_min_profit: number;
  default_min_roi: number;
  fuel_pence_per_mile: number;
  ship_small: number;
  ship_medium: number;
  ship_high_value: number;
  high_value_threshold: number;
  ebay_seller_type: "private" | "business";
  ebay_business_fee_pct: number;
  ebay_business_fixed_fee: number;
  ebay_private_fee_pct: number;
  ebay_promoted_pct: number;
  fb_local_factor: number;
  fb_active_discount: number;
  cex_payout: "cash" | "voucher";
  cex_dropoff_miles: number;
  fb_c_user: string;
  fb_xs: string;
  fb_cookie_configured?: boolean;
  ebay_client_id: string;
  ebay_client_secret: string;
  ebay_api_configured?: boolean;
}

export interface EbayTestResult {
  ok: boolean;
  message: string;
  sample?: { title: string; price: number; url: string }[];
}

export type WatchStatus = "watching" | "purchased" | "listed" | "sold";

export interface WatchlistItem {
  id: number;
  listing_id: string;
  source: SourceName;
  title: string;
  url: string;
  image_url: string | null;
  buy_price: number;
  best_channel: ExitName | null;
  best_profit: number | null;
  status: WatchStatus;
  notes: string;
  actual_buy_price: number | null;
  actual_sale_price: number | null;
  realised_profit: number | null;
  deal: Deal | null;
  created_at: string;
  updated_at: string;
}

export interface Health {
  ok: boolean;
  demo_mode: boolean;
  ebay_api: boolean;
  fb_cookies: boolean;
  playwright: boolean;
}
