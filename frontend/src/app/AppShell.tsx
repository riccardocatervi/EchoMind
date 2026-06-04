import { LogOut, Network } from "lucide-react";
import { Link, Outlet } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { useAuth } from "@/features/auth/hooks/useAuth";

/**
 * Guscio dell'area autenticata: topbar fissa + <Outlet/> per le rotte figlie.
 * E' una "layout route" del router.
 */
export function AppShell() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-14 items-center justify-between gap-2">
          <Link to="/" className="flex items-center gap-2">
            <Network className="size-5 text-primary" aria-hidden="true" />
            <span className="font-mono text-lg font-semibold tracking-tight">EchoMind</span>
          </Link>
          <div className="flex items-center gap-3">
            {user?.email && (
              <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
            )}
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut aria-hidden="true" />
              Esci
            </Button>
          </div>
        </div>
      </header>
      <main className="container py-8">
        <Outlet />
      </main>
    </div>
  );
}
