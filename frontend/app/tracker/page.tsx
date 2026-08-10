"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Match } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const COLUMNS: { key: string; label: string; hint: string; accent: string }[] = [
  { key: "approved", label: "Saved", hint: "shortlisted to apply", accent: "var(--brand)" },
  { key: "applied", label: "Applied", hint: "application submitted", accent: "var(--strong)" },
  { key: "rejected", label: "Skipped", hint: "not pursuing", accent: "var(--faint)" },
];

function Card({ m, onMove }: { m: Match; onMove: (id: number, s: string) => void }) {
  return (
    <div className="card p-3.5">
      <div className="flex items-start justify-between gap-2">
        <Link href={`/matches/${m.id}`} className="text-sm font-medium leading-snug hover:text-brand">
          {m.title}
        </Link>
        <span className="font-mono text-xs text-muted">{m.score}</span>
      </div>
      <p className="mt-0.5 text-xs text-muted">{m.company}</p>
      <div className="mt-2.5 flex gap-2 text-xs">
        {m.status !== "applied" && (
          <button onClick={() => onMove(m.id, "applied")} className="text-strong hover:underline">→ Applied</button>
        )}
        {m.status !== "approved" && (
          <button onClick={() => onMove(m.id, "approved")} className="text-brand hover:underline">→ Saved</button>
        )}
        {m.status !== "rejected" && (
          <button onClick={() => onMove(m.id, "rejected")} className="text-faint hover:underline">→ Skip</button>
        )}
      </div>
    </div>
  );
}

export default function TrackerPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<Match[]>([]);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) api.listMatches().then(setItems).catch(() => {});
  }, [user]);

  async function move(id: number, status: string) {
    const updated = await api.setMatchStatus(id, status);
    setItems((prev) => prev.map((m) => (m.id === id ? { ...m, status: updated.status } : m)));
  }

  if (loading || !user) return <div className="mx-auto max-w-5xl px-4 py-10 text-sm text-muted">Loading…</div>;

  const tracked = items.filter((m) => m.status !== "new");

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16">
      <div className="mb-6">
        <div className="eyebrow mb-1">Pipeline</div>
        <h1 className="font-display text-2xl font-bold">Application tracker</h1>
        <p className="mt-1 text-sm text-muted">Move roles across stages as you progress.</p>
      </div>

      {tracked.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-sm text-muted">
            Nothing tracked yet. Save roles from{" "}
            <Link href="/dashboard" className="text-brand hover:underline">Matches</Link> to build your pipeline.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const cards = tracked.filter((m) => m.status === col.key);
            return (
              <div key={col.key} className="rounded-xl border border-border-soft bg-panel/40 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: col.accent }} />
                  <h2 className="font-display text-sm font-semibold">{col.label}</h2>
                  <span className="font-mono text-xs text-faint">{cards.length}</span>
                </div>
                <p className="mb-3 text-xs text-faint">{col.hint}</p>
                <div className="space-y-2.5">
                  {cards.map((m) => <Card key={m.id} m={m} onMove={move} />)}
                  {cards.length === 0 && <p className="py-4 text-center text-xs text-faint">—</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
