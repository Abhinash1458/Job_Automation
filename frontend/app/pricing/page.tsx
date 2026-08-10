"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, BillingMe, Plan } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function limit(v: number) {
  return v < 0 ? "∞" : String(v);
}

export default function PricingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    api.plans().then(setPlans).catch(() => {});
    if (user) api.billingMe().then(setBilling).catch(() => {});
  }, [user]);

  async function upgrade(code: string) {
    setBusy(code);
    setError("");
    setMsg("");
    try {
      const order = await api.checkout(code);
      if (order.is_mock) {
        const updated: BillingMe = await api.confirm(order.order_id);
        setBilling(updated);
        setMsg(`You're on ${updated.plan_name} now. (Mock checkout — no live gateway configured.)`);
      } else {
        setMsg("Razorpay checkout would open here (live keys configured).");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  if (loading || !user) return <div className="mx-auto max-w-4xl px-4 py-10 text-sm text-muted">Loading…</div>;

  const currentPlan = billing?.plan || "free";
  const u = billing?.usage;

  return (
    <main className="mx-auto max-w-4xl px-4 pb-16">
      <div className="mb-6">
        <div className="eyebrow mb-1">Billing</div>
        <h1 className="font-display text-2xl font-bold">Plans &amp; pricing</h1>
        {u && (
          <p className="mt-2 text-sm text-muted">
            You're on <span className="font-medium text-text">{u.plan_name}</span>. Today:{" "}
            <span className="font-mono">{u.runs_used}/{limit(u.runs_limit)}</span> runs ·{" "}
            <span className="font-mono">{u.tailors_used}/{limit(u.tailors_limit)}</span> packets.
          </p>
        )}
      </div>

      {msg && <div className="mb-5 rounded-xl border border-strong/30 bg-strong/10 px-4 py-3 text-sm text-strong">{msg}</div>}
      {error && <div className="mb-5 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {plans.map((p) => {
          const isCurrent = p.code === currentPlan;
          const isPro = p.code === "pro";
          return (
            <div
              key={p.code}
              className={`card relative p-6 ${isPro ? "ring-1 ring-brand/40" : ""}`}
              style={isPro ? { background: "linear-gradient(180deg, rgba(124,135,255,.06), transparent 60%)" } : undefined}
            >
              {isPro && (
                <span className="absolute right-5 top-5 chip chip-brand">Most popular</span>
              )}
              <h3 className="font-display text-lg font-bold">{p.name}</h3>
              <div className="mt-1 flex items-baseline gap-1">
                <span className="font-display text-3xl font-bold">₹{p.price_inr}</span>
                <span className="text-sm text-muted">/month</span>
              </div>
              <ul className="mt-5 space-y-2.5 text-sm text-muted">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-strong">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                {isCurrent ? (
                  <span className="chip">Current plan</span>
                ) : p.price_inr === 0 ? (
                  <span className="chip">Free tier</span>
                ) : (
                  <button onClick={() => upgrade(p.code)} disabled={busy === p.code} className="btn btn-primary w-full">
                    {busy === p.code ? "Processing…" : `Upgrade to ${p.name}`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-6 text-center text-xs text-faint">
        Payments via Razorpay. Cancel anytime. Prices in INR.
      </p>
    </main>
  );
}
