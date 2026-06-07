import { Network } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";

import { buttonVariants } from "@/shared/components/ui/button";
import { Footer } from "@/shared/components/Footer";
import { GraphBackground } from "@/shared/components/GraphBackground";
import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";
import { ThemeToggle } from "@/shared/components/ThemeToggle";
import { TypewriterText } from "@/shared/components/TypewriterText";
import { useAuth } from "@/features/auth/hooks/useAuth";

/**
 * Schermata pubblica prima dell'autenticazione.
 *
 * Layout: sfondo animato full-viewport + contenuto centrato.
 * - Logo EchoMind in alto
 * - Frase typewriter dinamica al centro
 * - Breve descrizione
 * - Pulsanti login / signup
 * - ThemeToggle + LanguageSwitcher in alto a destra
 */
export function LandingPage() {
  const { t } = useTranslation();
  const { status } = useAuth();

  // Utente gia' autenticato: redirect diretto alla dashboard
  if (status === "authenticated") return <Navigate to="/documents" replace />;

  const phrases: string[] = JSON.parse(t("landing.phrases")) as string[];

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      <GraphBackground />

      {/* Barra superiore: logo + controlli */}
      <header className="relative z-10 flex items-center justify-between px-6 py-4 sm:px-10">
        <div className="flex items-center gap-2">
          <Network className="size-5 text-primary" aria-hidden="true" />
          <span className="font-mono text-lg font-semibold tracking-tight">EchoMind</span>
        </div>
        <div className="flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </header>

      {/* Contenuto principale centrato */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        {/* Typewriter -- frase dinamica in evidenza */}
        <p className="mb-6 min-h-[2.5rem] font-mono text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">
          <TypewriterText phrases={phrases} typeSpeed={50} deleteSpeed={25} pauseMs={2000} />
        </p>

        {/* Tagline fissa: la parte chiave e' colorata con text-primary */}
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
          {t("landing.tagline.before")}
          <span className="text-primary">{t("landing.tagline.highlight")}</span>
          {t("landing.tagline.after")}
        </h1>

        {/* Descrizione breve */}
        <p className="mb-10 max-w-xl text-base text-muted-foreground sm:text-lg">
          {t("landing.description")}
        </p>

        {/* CTA: uso buttonVariants su Link per evitare asChild (Button locale non usa Radix Slot) */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link to="/login" className={buttonVariants({ size: "lg" }) + " min-w-[140px]"}>
            {t("landing.login")}
          </Link>
          <Link
            to="/signup"
            className={buttonVariants({ variant: "outline", size: "lg" }) + " min-w-[140px]"}
          >
            {t("landing.signup")}
          </Link>
        </div>
      </main>

      <Footer />
    </div>
  );
}
