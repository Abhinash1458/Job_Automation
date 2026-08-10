"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "motion/react";
import { api, MatchDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ScoreMeter from "@/components/ScoreMeter";

export default function MatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();
  const [m, setM] = useState<MatchDetail | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) api.getMatch(Number(id)).then(setM).catch((e) => setError(e.message));
  }, [user, id]);

  async function generate() {
    setTailoring(true);
    setError("");
    try {
      setM(await api.tailorMatch(Number(id)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTailoring(false);
    }
  }

  async function setStatus(status: string) {
    const updated = await api.setMatchStatus(Number(id), status);
    setM((prev) => (prev ? { ...prev, status: updated.status } : prev));
  }

  if (loading || !user || !m) return <div className="mx-auto max-w-3xl px-4 py-10 text-sm text-muted">Loading…</div>;

  const hasPacket = !!m.cover_letter;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-16">
      <button onClick={() => router.back()} className="mb-4 text-sm text-muted transition hover:text-text">
        ← Back to matches
      </button>

      {error && <div className="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}

      {/* Header */}
      <div className="card mb-6 p-6">
        <div className="flex items-start gap-5">
          <ScoreMeter score={m.score} size={72} showLabel />
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-xl font-bold leading-tight">{m.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
              <span className="text-text/90">{m.company}</span>
              <span className="text-faint">·</span>
              <span>{m.location}</span>
              {m.source && <span className="chip ml-1">{m.source}</span>}
            </div>
          </div>
        </div>

        {m.reasons.length > 0 && (
          <div className="mt-5">
            <div className="eyebrow mb-2">Why it fits</div>
            <ul className="space-y-1.5 text-sm text-muted">
              {m.reasons.map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-strong/80" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {m.missing.length > 0 && (
          <div className="mt-4">
            <div className="eyebrow mb-2">Gaps to address</div>
            <div className="flex flex-wrap gap-1.5">
              {m.missing.map((g, i) => (
                <span key={i} className="chip chip-good">{g}</span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <a href={m.url} target="_blank" rel="noreferrer" className="btn btn-primary btn-sm">Open posting ↗</a>
          <button onClick={() => setStatus("approved")} className="btn btn-success btn-sm">
            {m.status === "approved" || m.status === "applied" ? "✓ Saved" : "Save"}
          </button>
          <button onClick={() => setStatus("applied")} className="btn btn-ghost btn-sm">
            {m.status === "applied" ? "✓ Applied" : "Mark applied"}
          </button>
        </div>
      </div>

      {/* Match breakdown */}
      {m.breakdown.length > 0 && (
        <div className="card mb-6 p-6">
          <div className="eyebrow mb-4">Why this score — match engine</div>
          <div className="space-y-3.5">
            {m.breakdown.map((f) => {
              const c = f.score >= 85 ? "var(--strong)" : f.score >= 70 ? "var(--good)" : f.score >= 55 ? "#c9a24b" : "var(--weak)";
              return (
                <div key={f.factor}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="text-text">{f.factor}</span>
                    <span className="truncate text-xs text-faint">{f.detail}</span>
                    <span className="font-mono text-xs" style={{ color: c }}>{f.score}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-ink">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: c }}
                      initial={{ width: 0 }}
                      animate={{ width: `${f.score}%` }}
                      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                    />
                  </div>
                  <div className="mt-0.5 text-right font-mono text-[10px] text-faint">weight {Math.round(f.weight * 100)}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tailored packet */}
      <div className="card p-6">
        <div className="mb-3 flex items-center justify-between">
          <div className="eyebrow">Tailored application packet</div>
          <button onClick={generate} disabled={tailoring} className="btn btn-primary btn-sm">
            {tailoring ? "Generating…" : hasPacket ? "Regenerate" : "Generate packet"}
          </button>
        </div>

        {!hasPacket && !tailoring && (
          <p className="text-sm text-muted">
            Generate a cover letter and pre-filled answers grounded in your CV — nothing invented.
          </p>
        )}
        {tailoring && (
          <div className="space-y-2">
            <div className="skeleton h-3 w-1/2" />
            <div className="skeleton h-24 w-full" />
          </div>
        )}

        {hasPacket && (
          <div className="space-y-6">
            {m.pitch && (
              <div>
                <div className="eyebrow mb-1.5">Fit pitch</div>
                <p className="text-sm text-text">{m.pitch}</p>
              </div>
            )}
            <div>
              <div className="eyebrow mb-1.5">Cover letter</div>
              <pre className="whitespace-pre-wrap rounded-xl border border-border-soft bg-ink p-4 font-sans text-sm text-text">
                {m.cover_letter}
              </pre>
            </div>
            {m.answers.length > 0 && (
              <div>
                <div className="eyebrow mb-2">Application answers</div>
                <div className="space-y-3">
                  {m.answers.map((qa, i) => (
                    <div key={i} className="rounded-xl border border-border-soft bg-ink/50 p-3">
                      <p className="text-sm font-medium text-text">{qa.question}</p>
                      <p className="mt-1 text-sm text-muted">{qa.answer}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
