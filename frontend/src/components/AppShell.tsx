import type { ReactNode } from "react";
import { Network } from "lucide-react";

interface AppShellProps {
  children: ReactNode;
}

/**
 * Guscio applicativo: topbar fissa + contenitore centrale. In CP4 ospitera' la
 * navigazione e l'<Outlet/> del router; per ora rende i figli passati.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
        <div className="container flex h-14 items-center gap-2">
          <Network className="size-5 text-primary" aria-hidden="true" />
          <span className="font-mono text-lg font-semibold tracking-tight">EchoMind</span>
        </div>
      </header>
      <main className="container py-8">{children}</main>
    </div>
  );
}
