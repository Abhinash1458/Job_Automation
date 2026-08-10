"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, BillingMe, Schedule } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function limit(v: number) {
  return v < 0 ? "∞" : String(v);
}

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [sched, setSched] = useState<Schedule | null>(null);
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [hour, setHour] = useState(1);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.getSchedule().then((s: Schedule) => { setSched(s); setHour(s.hour_utc); });
    api.billingMe().then(setBilling).catch(() => {});
  }, [user]);

  async function save(enabled: boolean) {
    setBusy(true); setError(""); setMsg("");
    try {
      const s = await api.updateSchedule(enabled, hour);
      setSched(s);
      setMsg(enabled ? "Daily scheduled runs are on." : "Scheduled runs turned off.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function runNow() {
    setBusy(true); setError(""); setMsg("");
    try {
      await api.runScheduledNow();
      setMsg("Triggered a run — check Matches in a moment.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  if (loading || !user) return <div className="mx-auto max-w-2xl px-4 py-10 text-sm text-muted">Loading…</div>;

  const allowed = sched?.scheduling_allowed;
  const u = billing?.usage;

  return (
    <main className="mx-auto max-w-2xl px-4 pb-16">
      <div className="mb-6">
        <div className="eyebrow mb-1">Account</div>
        <h1 className="font-display text-2xl font-bold">Settings</h1>
      </div>

      {msg && <div className="mb-4 rounded-xl border border-strong/30 bg-strong/10 px-4 py-3 text-sm text-strong">{msg}</div>}
      {error && <div className="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}

      {/* Plan & usage */}
      {u && (
        <section className="card mb-5 p-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="eyebrow">Plan &amp; usage</div>
            <Link href="/pricing" className="text-sm text-brand hover:underline">Manage →</Link>
          </div>
          <p className="text-sm">
            <span className="text-muted">Current plan:</span>{" "}
            <span className={`chip ${u.plan === "pro" ? "chip-brand" : ""}`}>{u.plan_name}</span>
          </p>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <UsageStat label="Match runs today" used={u.runs_used} cap={u.runs_limit} />
            <UsageStat label="Tailored packets today" used={u.tailors_used} cap={u.tailors_limit} />
          </div>
        </section>
      )}

      {/* Scheduling */}
      <section className="card p-6">
        <div className="mb-2 flex items-center justify-between">
          <div className="eyebrow">Automated daily runs</div>
          {!allowed && <span className="chip chip-brand">Pro</span>}
        </div>
        <p className="mb-4 text-sm text-muted">Run a fresh job match automatically every day at your chosen time (UTC).</p>

        {!allowed ? (
          <p className="text-sm text-muted">
            A Pro feature.{" "}
            <Link href="/pricing" className="text-brand hover:underline">Upgrade to enable it →</Link>
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted">Run daily at</label>
              <select value={hour} onChange={(e) => setHour(Number(e.target.value))} className="input w-auto py-1.5">
                {Array.from({ length: 24 }, (_, h) => (
                  <option key={h} value={h}>{String(h).padStart(2, "0")}:00 UTC</option>
                ))}
              </select>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {sched?.enabled ? (
                <>
                  <button onClick={() => save(true)} disabled={busy} className="btn btn-ghost btn-sm">Save time</button>
                  <button onClick={() => save(false)} disabled={busy} className="btn btn-ghost btn-sm">Turn off</button>
                </>
              ) : (
                <button onClick={() => save(true)} disabled={busy} className="btn btn-primary btn-sm">Enable daily runs</button>
              )}
              <button onClick={runNow} disabled={busy} className="btn btn-success btn-sm">Run now</button>
            </div>
            <p className="font-mono text-xs text-faint">
              {sched?.enabled ? `on · ${String(sched.hour_utc).padStart(2, "0")}:00 UTC` : "off"}
              {sched?.last_run_date ? ` · last ${sched.last_run_date}` : ""}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

function UsageStat({ label, used, cap }: { label: string; used: number; cap: number }) {
  const pct = cap < 0 ? 8 : Math.min(100, (used / Math.max(cap, 1)) * 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-faint">{used}/{limit(cap)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink">
        <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
