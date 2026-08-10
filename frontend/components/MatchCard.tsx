"use client";
import { useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { api, Match } from "@/lib/api";
import ScoreMeter from "./ScoreMeter";

export default function MatchCard({ match, rank }: { match: Match; rank?: number }) {
  const [status, setStatus] = useState(match.status);
  const [busy, setBusy] = useState(false);
  const reduce = useReducedMotion();

  async function decide(next: string) {
    setBusy(true);
    try {
      const updated = await api.setMatchStatus(match.id, next);
      setStatus(updated.status);
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      whileHover={reduce ? undefined : { y: -3 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={`card p-5 ${status === "rejected" ? "opacity-55" : ""}`}
    >
      <div className="flex gap-4">
        <div className="flex flex-col items-center gap-2 pt-0.5">
          {rank != null && <span className="eyebrow">#{rank}</span>}
          <ScoreMeter score={match.score} />
        </div>

        <div className="min-w-0 flex-1">
          <Link href={`/matches/${match.id}`} className="font-display text-[15px] font-semibold leading-snug hover:text-brand">
            {match.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            <span className="text-text/90">{match.company}</span>
            <span className="text-faint">·</span>
            <span>{match.location}</span>
            {match.source && <span className="chip ml-1">{match.source}</span>}
          </div>

          {match.reasons.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm text-muted">
              {match.reasons.slice(0, 3).map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand/70" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
          {match.missing.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {match.missing.slice(0, 3).map((g, i) => (
                <span key={i} className="chip chip-good">{g}</span>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a href={match.url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
              Open posting ↗
            </a>
            <button
              disabled={busy || status === "approved"}
              onClick={() => decide("approved")}
              className="btn btn-success btn-sm"
            >
              {status === "approved" ? "✓ Saved" : "Save"}
            </button>
            <button
              disabled={busy || status === "rejected"}
              onClick={() => decide("rejected")}
              className="btn btn-ghost btn-sm"
            >
              Skip
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
