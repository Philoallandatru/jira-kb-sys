import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jira Summary Frontend",
  description: "Retro-modern Jira, spec, and policy control deck.",
};

const navItems = [
  { href: "/tasks", label: "Task Center" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/reports", label: "Daily Reports" },
  { href: "/issues", label: "Issues" },
  { href: "/docs-qa", label: "Docs QA" },
  { href: "/jira-docs-qa", label: "Jira + Docs QA" },
  { href: "/management-summary", label: "Management Summary" },
  { href: "/settings", label: "Prompt Settings" },
];

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <header className="topbar">
            <div className="brand">
              <Link href="/" className="brand-title">
                Jira Control Deck
              </Link>
              <div className="brand-subtitle">
                A retro-modern workspace for Jira snapshots, specs, policy, and management reporting.
              </div>
            </div>
            <div className="badge-row">
              <span className="badge">Vintage Ops</span>
              <span className="badge">Modern AI</span>
              <span className="badge">Management</span>
            </div>
          </header>
          <nav className="section-nav" aria-label="Primary">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="nav-pill">
                {item.label}
              </Link>
            ))}
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
