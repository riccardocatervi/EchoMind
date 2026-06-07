import { useEffect, useRef } from "react";
import { LogOut, Network, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Outlet } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Footer } from "@/shared/components/Footer";
import { GraphBackground } from "@/shared/components/GraphBackground";
import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";
import { ThemeToggle } from "@/shared/components/ThemeToggle";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useProfile } from "@/features/profile/api/queries";

/**
 * Guscio dell'area autenticata: topbar sticky + sfondo animato + <Outlet/> + Footer.
 *
 * Stacking (z-index):
 *  - GraphBackground: fixed z-0
 *  - header:          sticky z-20
 *  - main content:    relative z-10
 *  - Footer:          relative z-10
 *
 * Header -- link al profilo:
 *  Icona UserRound sempre visibile + nome (o email) come testo solo su lg+.
 *  In questo modo non c'e' duplicazione: un singolo elemento cliccabile.
 *
 * Logout:
 *  signOut() aggiorna lo store Supabase -> ProtectedRoute rileva
 *  "unauthenticated" e redirige a "/" automaticamente. Nessuna race condition.
 */
export function AppShell() {
  const { user, signOut } = useAuth();
  const { t, i18n } = useTranslation();
  const { data: profile } = useProfile();

  // Sincronizza la lingua al LOGIN: applica la preferenza salvata sul profilo
  // la prima volta che il profilo diventa disponibile nella sessione corrente.
  //
  // Il ref impedisce che refetch successivi (window focus, navigazione) tornino
  // a sovrascrivere una lingua cambiata dall'utente nella stessa sessione.
  // Il ref si azzera al dismount (logout/remount): il prossimo login riapplica
  // la preferenza salvata correttamente.
  const didSyncLanguageRef = useRef(false);
  useEffect(() => {
    if (profile?.preferred_language && !didSyncLanguageRef.current) {
      didSyncLanguageRef.current = true;
      if (profile.preferred_language !== i18n.language) {
        void i18n.changeLanguage(profile.preferred_language);
      }
    }
  }, [profile?.preferred_language, i18n]);

  // Recupera il nome da user_metadata (salvato al signup).
  // Se non disponibile, mostra l'email come fallback.
  const firstName = (user?.user_metadata?.first_name as string | undefined) ?? "";
  const profileLabel = firstName || (user?.email ?? "");

  function handleSignOut() {
    // ProtectedRoute gestisce il redirect a "/" quando lo stato diventa "unauthenticated"
    void signOut();
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <GraphBackground />

      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-14 items-center justify-between gap-2">
          {/* Logo */}
          <Link to="/documents" className="flex shrink-0 items-center gap-2">
            <Network className="size-5 text-primary" aria-hidden="true" />
            <span className="font-mono text-lg font-semibold tracking-tight">EchoMind</span>
          </Link>

          {/* Controlli destra */}
          <div className="flex items-center gap-1 sm:gap-2">
            <LanguageSwitcher />
            <ThemeToggle />

            {/*
             * Profilo: icona + nome/email in un unico link.
             * Il testo e' visibile solo su schermi lg+ (hidden lg:inline),
             * cosi' su mobile rimane solo l'icona senza duplicazioni.
             */}
            <Link
              to="/profile"
              className="inline-flex h-9 items-center gap-1.5 rounded-md px-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              title={t("app.profile")}
            >
              <UserRound className="size-4 shrink-0" aria-hidden="true" />
              <span className="hidden max-w-[160px] truncate lg:inline">{profileLabel}</span>
            </Link>

            <Button variant="ghost" size="sm" onClick={handleSignOut}>
              <LogOut className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">{t("app.logout")}</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="container relative z-10 flex-1 py-8">
        <Outlet />
      </main>

      <Footer />
    </div>
  );
}
