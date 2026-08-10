"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Logo from "./Logo";

const LINKS = [
  { href: "/dashboard", label: "Matches" },
  { href: "/tracker", label: "Tracker" },
  { href: "/report", label: "Report" },
  { href: "/settings", label: "Settings" },
  { href: "/pricing", label: "Pricing" },
];

function initials(name: string, email: string) {
  const n = (name || "").trim();
  if (n) return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (email[0] || "?").toUpperCase();
}

export default function Nav() {
  const { user, logout } = useAuth();
  const path = usePathname();
  const [plan, setPlan] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [showBar, setShowBar] = useState(true);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.billingMe().then((b) => setPlan(b.plan_name)).catch(() => {});
  }, []);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const isFree = plan !== "Pro";

  return (
    <header className="sticky top-0 z-30">
      {/* Announcement / utility bar */}
      {showBar && (
        <div className="relative bg-gradient-to-r from-brand to-brand-2 text-white">
          <div className="mx-auto flex max-w-5xl items-center justify-center gap-2 px-4 py-1.5 text-center text-xs">
            <span className="opacity-95">
              {isFree
                ? "Now searching Startup, Product, GCC & Service-based roles —"
                : "You're on Pro — daily auto-runs & 50 tailored packets a day."}
            </span>
            {isFree && (
              <Link href="/pricing" className="font-semibold underline underline-offset-2 hover:opacity-90">
                Unlock daily auto-runs →
              </Link>
            )}
          </div>
          <button
            onClick={() => setShowBar(false)}
            aria-label="Dismiss"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-white/70 transition hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {/* Main nav */}
      <div className="border-b border-border-soft bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
          <Link href="/dashboard" aria-label="JobHunt home">
            <Logo />
          </Link>

          <nav className="ml-2 flex flex-1 items-center gap-1 overflow-x-auto">
            {LINKS.map((l) => {
              const active = path === l.href || (l.href !== "/dashboard" && path.startsWith(l.href));
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`relative whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    active ? "text-text" : "text-muted hover:text-text"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-lg bg-elevated"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span className="relative z-10">{l.label}</span>
                </Link>
              );
            })}
          </nav>

          {plan && (
            <span className={`chip ${plan === "Pro" ? "chip-brand" : ""} hidden sm:inline-flex`}>
              {plan}
            </span>
          )}

          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setOpen((o) => !o)}
              className="grid h-9 w-9 place-items-center rounded-full bg-elevated text-sm font-semibold text-text ring-1 ring-border transition hover:ring-brand"
              aria-label="Account menu"
            >
              {user ? initials(user.full_name, user.email) : "?"}
            </button>
            {open && (
              <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-panel shadow-lift">
                <div className="border-b border-border-soft px-4 py-3">
                  <div className="truncate text-sm text-text">{user?.email}</div>
                  <div className="eyebrow mt-1">{plan || "Free"} plan</div>
                </div>
                <Link href="/settings" className="block px-4 py-2.5 text-sm text-muted hover:bg-elevated hover:text-text" onClick={() => setOpen(false)}>
                  Settings
                </Link>
                <Link href="/pricing" className="block px-4 py-2.5 text-sm text-muted hover:bg-elevated hover:text-text" onClick={() => setOpen(false)}>
                  Plans &amp; billing
                </Link>
                <button
                  onClick={() => { setOpen(false); logout(); }}
                  className="block w-full px-4 py-2.5 text-left text-sm text-danger hover:bg-elevated"
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
