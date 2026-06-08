import type { ReactNode } from "react";
import { Network } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Footer } from "@/shared/components/Footer";
import { GraphBackground } from "@/shared/components/GraphBackground";
import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";
import { ThemeToggle } from "@/shared/components/ThemeToggle";

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
  /**
   * Icona mostrata in cima alla card, sopra titolo e descrizione.
   * Predefinita: icona Network di Lucide.
   * Passa un componente personalizzato (es. YetiAvatar) per sostituirla.
   */
  icon?: ReactNode;
}

/**
 * Layout per le pagine di autenticazione (login / signup / forgot / reset).
 *
 * Struttura:
 *  - flex-col min-h-screen: la card occupa lo spazio centrale (flex-1),
 *    il Footer si ancora in fondo senza position:absolute.
 *  - ThemeToggle / LanguageSwitcher: absolute in alto a destra.
 *
 * Stacking (z-index):
 *  - GraphBackground: fixed z-0 -- sopra bg-background, sotto tutto
 *  - controlli tema/lingua: absolute z-10
 *  - Card: relative z-10 -- sopra il canvas
 *  - Footer: relative z-10
 */
export function AuthShell({ title, description, children, icon }: AuthShellProps) {
  return (
    <div className="relative flex min-h-screen flex-col bg-background px-4">
      <GraphBackground />

      {/* Controlli tema / lingua in alto a destra.
       * z-20 > z-10 del container della card (flex-1): evita che il container
       * (che copre l'intera viewport) intercetti i click sui bottoni. */}
      <div className="absolute right-4 top-4 z-20 flex items-center gap-1">
        <LanguageSwitcher />
        <ThemeToggle />
      </div>

      {/* Area centrale: la card si centra nello spazio disponibile */}
      <div className="relative z-10 flex flex-1 items-center justify-center py-16">
        {/*
         * Glow: `shadow-[0_0_50px_rgba(99,120,220,0.22)]` crea l'alone blu-indaco.
         * `ring-1 ring-white/5`: bordo sottile per separare la card dallo sfondo.
         */}
        <Card className="w-full max-w-sm shadow-[0_0_50px_rgba(99,120,220,0.22)] ring-1 ring-white/5">
          <CardHeader className="space-y-3 text-center">
            <div className="flex justify-center">
              {icon ?? <Network className="size-8 text-primary" aria-hidden="true" />}
            </div>
            <div className="space-y-1">
              <CardTitle className="font-mono text-2xl">{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </div>
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
      </div>

      <Footer />
    </div>
  );
}
