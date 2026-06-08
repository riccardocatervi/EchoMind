/**
 * Footer condiviso -- appare su tutte le pagine (LandingPage, AuthShell, AppShell).
 *
 * Contiene: nome del prodotto, autore, licenza e anno.
 * Le entita' HTML (mdash, middot) rendono i caratteri speciali senza unicode
 * nei sorgenti, compatibile con qualsiasi editor.
 */
export function Footer() {
  return (
    <footer className="relative z-10 border-t py-4 text-center text-xs text-muted-foreground">
      <p>EchoMind &mdash; Knowledge Graph Platform</p>
      <p className="mt-0.5">Riccardo Catervi &middot; MIT License &middot; 2026</p>
    </footer>
  );
}
