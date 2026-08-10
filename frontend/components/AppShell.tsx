"use client";
import { usePathname } from "next/navigation";
import Nav from "./Nav";

// Routes that render without the app chrome (auth + landing).
const BARE = new Set(["/", "/login", "/register"]);

// Persistent app shell: the header is rendered ONCE here, above the page
// transition, so it stays static (no remount/flicker) across navigations.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (BARE.has(path)) return <>{children}</>;
  return (
    <>
      <Nav />
      <div className="pt-8">{children}</div>
    </>
  );
}
