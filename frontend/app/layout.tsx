import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jira Summary Frontend",
  description: "复古现代风格的 Jira KB 控制台",
};

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
              <div className="brand-subtitle">复古现代风格的 Jira / Spec / Policy 智能控制台</div>
            </div>
            <div className="badge-row">
              <span className="badge">Vintage Ops</span>
              <span className="badge">Modern AI</span>
              <span className="badge">Management</span>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
