"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { api, Match, MatchRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import MatchCard from "@/components/MatchCard";

type Profile = { resume_filename: string; data: any } | null;

const COMPANY_LABELS: Record<string, string> = {
  any: "All", gcc: "GCC / Captive", product: "Product", startup: "Startup", service: "Service-based",
};
const JOB_LABELS: Record<string, string> = {
  any: "Any type", full_time: "Full-time", contract: "Contract", remote: "Remote",
};

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<Profile>(null);
  const [uploading, setUploading] = useState(false);
  const [run, setRun] = useState<MatchRun | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState("");
  const [limitHit, setLimitHit] = useState(false);
  const [searched, setSearched] = useState(false);

  const [companyTypes, setCompanyTypes] = useState<string[]>(["any", "gcc", "product", "startup", "service"]);
  const [jobTypes, setJobTypes] = useState<string[]>(["any", "full_time", "contract", "remote"]);
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("Bangalore");
  const [companyType, setCompanyType] = useState("gcc");
  const [jobType, setJobType] = useState("any");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.getProfile().then((p) => {
      setProfile(p);
      if (p?.data?.headline) setRole(p.data.headline.split(/[|,]/)[0].trim());
    }).catch(() => {});
    api.matchOptions().then((o) => { setCompanyTypes(o.company_types); setJobTypes(o.job_types); }).catch(() => {});
    api.latestRun().then((r: MatchRun | null) => {
      if (r) {
        setRun(r);
        if (r.status === "done") { setSearched(true); api.runResults(r.id).then(setMatches); }
        else if (r.status === "running" || r.status === "pending") { setSearched(true); startPolling(r.id); }
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const startPolling = useCallback((runId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const r: MatchRun = await api.getRun(runId);
      setRun(r);
      if (r.status === "done") { if (pollRef.current) clearInterval(pollRef.current); setMatches(await api.runResults(runId)); }
      else if (r.status === "error") { if (pollRef.current) clearInterval(pollRef.current); setError(r.error || "Search failed."); }
    }, 2000);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const p = await api.uploadCV(file);
      setProfile(p);
      if (p?.data?.headline) setRole(p.data.headline.split(/[|,]/)[0].trim());
    } catch (err) { setError((err as Error).message); }
    finally { setUploading(false); }
  }

  async function search() {
    setError(""); setLimitHit(false); setMatches([]); setSearched(true);
    const keywords = role.split(",").map((k) => k.trim()).filter(Boolean);
    try {
      const r: MatchRun = await api.startRun({
        company_type: companyType, job_type: jobType,
        keywords: keywords.length ? keywords : undefined,
        location: location.trim() || undefined,
      });
      setRun(r); startPolling(r.id);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      if (/limit reached|Upgrade/i.test(msg)) setLimitHit(true);
    }
  }

  if (loading || !user) return <div className="mx-auto max-w-5xl px-4 py-10 text-sm text-muted">Loading…</div>;

  const running = run?.status === "running" || run?.status === "pending";

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16">

      <div className="mb-6">
        <div className="eyebrow mb-1">Search</div>
        <h1 className="font-display text-[28px] font-bold leading-tight">Roles matched to your CV</h1>
        <p className="mt-1 text-sm text-muted">Search live openings — ranked by how well they fit you.</p>
      </div>

      {/* CV status bar */}
      <div className="card mb-4 flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
        {profile ? (
          <>
            <div className="flex min-w-0 items-center gap-2 text-sm">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-strong/15 text-[11px] text-strong">✓</span>
              <span className="truncate font-medium text-text">{profile.resume_filename}</span>
              {profile.data?.headline && <span className="hidden truncate text-muted sm:inline">· {profile.data.headline}</span>}
            </div>
            <label className="cursor-pointer text-sm text-brand hover:underline">
              Replace CV
              <input type="file" accept=".pdf,.docx,.doc,.txt,.md" onChange={onUpload} className="hidden" />
            </label>
          </>
        ) : (
          <>
            <span className="text-sm text-muted">Upload your CV so we can score every role against it.</span>
            <label className="btn btn-primary btn-sm cursor-pointer">
              {uploading ? "Parsing…" : "Upload CV"}
              <input type="file" accept=".pdf,.docx,.doc,.txt,.md" onChange={onUpload} className="hidden" />
            </label>
          </>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}{limitHit && <>{" "}<Link href="/pricing" className="font-medium underline">Upgrade to Pro →</Link></>}
        </div>
      )}

      {/* Search bar */}
      <div className="card mb-8 p-5">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <div className="label">Role</div>
            <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="AI Engineer, ML Engineer"
              className="input" onKeyDown={(e) => e.key === "Enter" && profile && !running && search()} />
          </div>
          <div className="sm:w-52">
            <div className="label">Location</div>
            <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Bangalore" className="input" />
          </div>
          <div className="flex items-end">
            <button onClick={search} disabled={!profile || running} className="btn btn-primary h-[42px] w-full sm:w-auto">
              {running ? "Searching…" : "Search jobs"}
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
          <FilterRow label="Company" opts={companyTypes} labels={COMPANY_LABELS} value={companyType} onChange={setCompanyType} />
          <FilterRow label="Engagement" opts={jobTypes} labels={JOB_LABELS} value={jobType} onChange={setJobType} />
        </div>
      </div>

      {/* Results */}
      {running && matches.length === 0 && <ResultsSkeleton />}

      {searched && !running && matches.length === 0 && (
        <div className="card p-10 text-center text-sm text-muted">
          No roles matched this search. Try a broader role, a different company type, or “All”.
        </div>
      )}

      {matches.length > 0 && (
        <>
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="font-display text-lg font-semibold">
              {matches.length} <span className="text-muted">roles</span>
            </h2>
            <span className="font-mono text-xs text-muted">
              {COMPANY_LABELS[companyType]} · {run?.location}
            </span>
          </div>
          <motion.div
            className="grid grid-cols-1 gap-4 lg:grid-cols-2"
            initial="hidden" animate="show"
            variants={{ hidden: {}, show: { transition: { staggerChildren: 0.04 } } }}
          >
            {matches.map((m, i) => (
              <motion.div key={m.id} variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }}>
                <MatchCard match={m} rank={i + 1} />
              </motion.div>
            ))}
          </motion.div>
        </>
      )}

      {!searched && !running && (
        <div className="card p-10 text-center">
          <p className="text-sm text-muted">
            {profile ? "Set your filters and hit Search jobs." : "Upload your CV above, then search."}
          </p>
        </div>
      )}
    </main>
  );
}

function FilterRow({
  label, opts, labels, value, onChange,
}: {
  label: string; opts: string[]; labels: Record<string, string>; value: string; onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs font-medium text-faint">{label}</span>
      {opts.map((o) => (
        <button key={o} onClick={() => onChange(o)}
          className={`btn btn-sm ${value === o ? "btn-primary" : "btn-ghost"}`}>
          {labels[o] || o}
        </button>
      ))}
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="card flex gap-4 p-5">
          <div className="skeleton h-14 w-14 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-2/3" />
            <div className="skeleton h-3 w-1/3" />
            <div className="skeleton h-3 w-5/6" />
          </div>
        </div>
      ))}
    </div>
  );
}
