export type Bet = {
  code?: string;
  name?: string;
  side?: string;
  why?: string;
};

export type Actor = {
  id?: string;
  name?: string;
  stance?: string;
  note?: string;
  think?: string;
  bets?: Bet[];
  pnl?: number | null;
  pnl_yuan?: number | null;
  cash?: number | null;
  starting?: number | null;
  rate?: number | null;
  settled?: boolean;
};

export type AiDesk = {
  model?: string;
  stance?: string;
  plan?: string;
  think?: string;
  note?: string;
  watch?: Bet[];
  avoid?: { code?: string; name?: string; why?: string }[];
};

export type EmBoard = {
  bk?: string;
  name: string;
  pct?: number | null;
  up?: number;
  down?: number;
  zt?: number;
  kind?: string;
  level?: string;
};

export type Stock = {
  code?: string;
  name?: string;
  boards?: number;
  y_boards?: number;
  pct?: number | null;
  open_pct?: number | null;
  today_pct?: number | null;
  match_pct?: number | null;
  turnover?: number;
  open_times?: number;
  first_seal?: string;
  float_mv_yi?: number;
  role?: string;
  verdict?: string;
  action?: string;
  theme?: string;
  industry?: string;
  industry_l1?: string;
  industry_l2?: string;
  industry_l3?: string;
  region?: string;
  concepts?: string[];
  boards_em?: EmBoard[];
  theme_count?: number;
  clustered?: boolean;
  vane?: string;
  army?: string;
  peers?: string[];
  reasons?: { tone?: string; text?: string }[];
  watch_note?: string;
  result?: string;
  watch_level?: string;
};

export type LiveData = {
  date?: string;
  phase?: string;
  phase_name?: string;
  phase_why?: string;
  max_board?: number;
  zt_count?: number;
  zb_count?: number;
  disclaimer?: string;
  fetch_error?: string;
  ledger_error?: string;
  session?: { id?: string; label?: string };
  auction?: {
    as_of?: string;
    stage?: string;
    session?: string;
    filled?: number;
    rows?: { code?: string; flag?: string }[];
  };
  ai?: AiDesk;
  picks?: { stance?: string; primary?: Stock[] };
  ladder?: { boards: number; stocks: Stock[] }[];
  themes?: { name: string; count: number; max_board: number; vane: string; army: string; clustered: boolean; members: string[] }[];
  limit_up?: Stock[];
  rules?: string[];
  yesterday?: {
    date?: string;
    count?: number;
    promoted_n?: number;
    failed_n?: number;
    rate?: number | null;
    preopen?: Stock[];
    auction_strong?: Stock[];
    auction_weak?: Stock[];
  };
  tomorrow?: { plan?: string };
  morning_watch?: Stock[];
  paper?: {
    note?: string;
    today?: { date?: string; phase?: string; settled?: boolean; actors?: Actor[] };
    scoreboard?: {
      id: string;
      name: string;
      days: number;
      wins: number;
      losses: number;
      pnl: number;
      pnl_yuan?: number;
      cash?: number;
      starting?: number;
      rate: number | null;
    }[];
    history?: { date: string; phase?: string; settled?: boolean; zt_count?: number; actors?: Actor[] }[];
    starting?: number;
    bet_size?: number;
  };
};
