"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, CareerReport } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ScoreMeter from "@/components/ScoreMeter";

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-xs text-faint">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink">
        <div
          className="h-full rounded-full"
          style={{ width: `${value}%`, background: "linear-gradient(90deg,var(--brand),var(--strong))", transition: "width .5s ease" }}
        />
      </div>
    </div>
  );
}

export default function ReportPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [r, setR] = useState<CareerReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) api.getReport().then(setR).catch((e) => setError(e.message));
  }, [user]);

  if (loading || !user) return <div className="mx-auto max-w-3xl px-4 py-10 text-sm text-muted">Loading…</div>;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-16">
      <div className="mb-6">
        <div className="eyebrow mb-1">Career intelligence</div>
        <h1 className="font-display text-2xl font-bold">Readiness report</h1>
      </div>

      {error && (
        <div className="card p-8 text-center text-sm text-muted">
          {error}{" "}
          <Link href="/dashboard" className="text-brand hover:underline">Upload a CV</Link> to generate it.
        </div>
      )}

      {r && (
        <div className="space-y-6">
          {/* Readiness hero */}
          <div className="card flex items-center gap-6 p-6">
            <ScoreMeter score={r.readiness} size={88} />
            <div>
              <div className="eyebrow mb-1">Overall readiness</div>
              <p className="font-display text-lg font-semibold">{r.readiness_label}</p>
              <p className="mt-1 text-sm text-muted">{r.headline} · {r.years_experience} yrs experience</p>
            </div>
          </div>

          {/* Dimensions */}
          <div className="card p-6">
            <div className="eyebrow mb-4">Readiness breakdown</div>
            <div className="space-y-4">
              {r.skill_bars.map((b) => <Bar key={b.label} label={b.label} value={b.value} />)}
            </div>
          </div>

          {/* Market snapshot */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { n: r.matches_analyzed, l: "roles analyzed" },
              { n: r.strong_matches, l: "strong fits" },
              { n: r.avg_score, l: "avg fit score" },
            ].map((s) => (
              <div key={s.l} className="card p-5 text-center">
                <div className="font-display text-2xl font-bold">{s.n}</div>
                <div className="eyebrow mt-1">{s.l}</div>
              </div>
            ))}
          </div>

          {/* Strengths + focus */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="card p-6">
              <div className="eyebrow mb-3">Your strengths</div>
              <div className="flex flex-wrap gap-1.5">
                {r.strengths.map((s) => <span key={s} className="chip chip-strong">{s}</span>)}
              </div>
            </div>
            <div className="card p-6">
              <div className="eyebrow mb-3">Focus areas</div>
              {r.focus_areas.length ? (
                <ul className="space-y-1.5 text-sm text-good">
                  {r.focus_areas.map((f) => (
                    <li key={f} className="flex gap-2">
                      <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-good/80" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-faint">Run a match to surface the gaps recruiters flag most.</p>
              )}
            </div>
          </div>

          {/* Targets + companies */}
          <div className="card p-6">
            <div className="eyebrow mb-3">Target roles &amp; companies</div>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {r.target_roles.map((t) => <span key={t} className="chip chip-brand">{t}</span>)}
            </div>
            {r.top_companies.length > 0 && (
              <p className="text-sm text-muted">
                Seen most in your matches: <span className="text-text/90">{r.top_companies.join(", ")}</span>
              </p>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
