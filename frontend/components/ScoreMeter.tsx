"use client";
import { useEffect, useState } from "react";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";

// Signature element: the match score as a number inside a gradient arc that
// springs up on mount, with the number counting up to match.
function tone(score: number) {
  if (score >= 85) return { c: "var(--strong)", label: "strong fit" };
  if (score >= 70) return { c: "var(--good)", label: "good fit" };
  if (score >= 55) return { c: "var(--fair)", label: "fair fit" };
  return { c: "var(--weak)", label: "weak fit" };
}

export default function ScoreMeter({
  score,
  size = 56,
  showLabel = false,
}: {
  score: number;
  size?: number;
  showLabel?: boolean;
}) {
  const { c, label } = tone(score);
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const reduce = useReducedMotion();

  const progress = useMotionValue(reduce ? score / 100 : 0);
  const dashoffset = useTransform(progress, (p) => circ * (1 - p));
  const [shown, setShown] = useState(reduce ? score : 0);

  useEffect(() => {
    if (reduce) { setShown(score); progress.set(score / 100); return; }
    const c1 = animate(progress, score / 100, { duration: 0.7, ease: [0.22, 1, 0.36, 1] });
    const c2 = animate(0, score, {
      duration: 0.7, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)),
    });
    return () => { c1.stop(); c2.stop(); };
  }, [score, reduce, progress, circ]);

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--border)" strokeWidth="3" fill="none" />
          <motion.circle
            cx={size / 2} cy={size / 2} r={r} stroke={c} strokeWidth="3" fill="none"
            strokeLinecap="round" strokeDasharray={circ} style={{ strokeDashoffset: dashoffset }}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center font-display font-bold tabular-nums"
          style={{ color: c, fontSize: size * 0.34 }}
        >
          {shown}
        </span>
      </div>
      {showLabel && <span className="eyebrow" style={{ color: c }}>{label}</span>}
    </div>
  );
}
