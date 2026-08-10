// Tiny typed fetch wrapper around the FastAPI backend.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "jh_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  window.localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export const api = {
  async register(email: string, password: string, full_name: string) {
    return handle(
      await fetch(`${BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name }),
      })
    );
  },

  async login(email: string, password: string) {
    // OAuth2 password form expects x-www-form-urlencoded with 'username'.
    const form = new URLSearchParams({ username: email, password });
    return handle(
      await fetch(`${BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form.toString(),
      })
    );
  },

  async me() {
    return handle(await fetch(`${BASE}/auth/me`, { headers: authHeaders() }));
  },

  async getProfile() {
    return handle(await fetch(`${BASE}/profile`, { headers: authHeaders() }));
  },

  async uploadCV(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    return handle(
      await fetch(`${BASE}/profile/upload`, {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      })
    );
  },

  async startRun(
    opts: { company_type?: string; job_type?: string; keywords?: string[]; location?: string } = {}
  ) {
    return handle(
      await fetch(`${BASE}/matches/run`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ company_type: "any", job_type: "any", ...opts }),
      })
    );
  },

  async matchOptions() {
    return handle(await fetch(`${BASE}/matches/options`, { headers: authHeaders() }));
  },

  async getRun(id: number) {
    return handle(await fetch(`${BASE}/matches/runs/${id}`, { headers: authHeaders() }));
  },

  async latestRun() {
    return handle(await fetch(`${BASE}/matches/runs/latest`, { headers: authHeaders() }));
  },

  async runResults(id: number) {
    return handle(await fetch(`${BASE}/matches/runs/${id}/results`, { headers: authHeaders() }));
  },

  async setMatchStatus(id: number, status: string) {
    return handle(
      await fetch(`${BASE}/matches/${id}?status=${status}`, {
        method: "PATCH",
        headers: authHeaders(),
      })
    );
  },

  async getMatch(id: number) {
    return handle(await fetch(`${BASE}/matches/${id}`, { headers: authHeaders() }));
  },

  async tailorMatch(id: number) {
    return handle(
      await fetch(`${BASE}/matches/${id}/tailor`, { method: "POST", headers: authHeaders() })
    );
  },

  async listMatches(status?: string) {
    const q = status ? `?status=${status}` : "";
    return handle(await fetch(`${BASE}/matches${q}`, { headers: authHeaders() }));
  },

  async getReport() {
    return handle(await fetch(`${BASE}/report`, { headers: authHeaders() }));
  },

  // --- Phase 3: billing ---
  async plans() {
    return handle(await fetch(`${BASE}/billing/plans`));
  },
  async billingMe() {
    return handle(await fetch(`${BASE}/billing/me`, { headers: authHeaders() }));
  },
  async checkout(plan_code: string) {
    return handle(
      await fetch(`${BASE}/billing/checkout`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ plan_code }),
      })
    );
  },
  async confirm(order_id: string, payment_id = "mock_payment", signature = "mock_signature") {
    return handle(
      await fetch(`${BASE}/billing/confirm`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ order_id, payment_id, signature }),
      })
    );
  },

  // --- Phase 3: schedule ---
  async getSchedule() {
    return handle(await fetch(`${BASE}/schedule`, { headers: authHeaders() }));
  },
  async updateSchedule(enabled: boolean, hour_utc: number) {
    return handle(
      await fetch(`${BASE}/schedule`, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, hour_utc }),
      })
    );
  },
  async runScheduledNow() {
    return handle(
      await fetch(`${BASE}/schedule/run-now`, { method: "POST", headers: authHeaders() })
    );
  },
};

export type Match = {
  id: number;
  url: string;
  title: string;
  company: string;
  location: string;
  source: string;
  score: number;
  verdict: string;
  reasons: string[];
  missing: string[];
  status: string;
};

export type MatchRun = {
  id: number;
  status: string;
  keywords: string;
  location: string;
  total: number;
  scored: number;
  error: string;
};

export type QA = { question: string; answer: string };

export type Factor = { factor: string; score: number; weight: number; detail: string };

export type MatchDetail = Match & {
  description: string;
  breakdown: Factor[];
  cover_letter: string;
  pitch: string;
  answers: QA[];
};

export type CareerReport = {
  headline: string;
  years_experience: number;
  readiness: number;
  readiness_label: string;
  strengths: string[];
  focus_areas: string[];
  target_roles: string[];
  skill_bars: { label: string; value: number }[];
  matches_analyzed: number;
  strong_matches: number;
  avg_score: number;
  top_companies: string[];
};

export type Plan = {
  code: string;
  name: string;
  price_inr: number;
  runs_per_day: number;
  tailors_per_day: number;
  scheduling: boolean;
  features: string[];
};

export type Usage = {
  plan: string;
  plan_name: string;
  runs_used: number;
  runs_limit: number;
  tailors_used: number;
  tailors_limit: number;
  scheduling: boolean;
};

export type BillingMe = { plan: string; plan_name: string; plan_expires: string | null; usage: Usage };
export type Schedule = { enabled: boolean; hour_utc: number; last_run_date: string; scheduling_allowed: boolean };
