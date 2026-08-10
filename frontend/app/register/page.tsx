"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Logo from "@/components/Logo";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(email, password, name);
      router.replace("/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm animate-rise">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Logo size={30} />
          <div>
            <div className="eyebrow mb-1">Start free</div>
            <h1 className="font-display text-2xl font-bold">Create your account</h1>
            <p className="mt-1 text-sm text-muted">Upload a CV, get scored matches in seconds.</p>
          </div>
        </div>

        <form onSubmit={submit} className="card p-7">
          {error && (
            <p className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
          <label className="label">Full name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="input mb-4" placeholder="Your name" />
          <label className="label">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="input mb-4" placeholder="you@company.com" />
          <label className="label">Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} className="input mb-6" placeholder="At least 8 characters" />
          <button disabled={busy} className="btn btn-primary w-full">
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-brand hover:underline">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
