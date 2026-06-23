/**
 * Configurazione Tailwind CSS v3 — design system EchoMind.
 *
 * Perché Tailwind e non CSS-in-JS (Styled Components, Emotion):
 *   Tailwind genera solo le classi effettivamente usate (tree-shaking via `content`).
 *   CSS-in-JS aggiunge runtime overhead (calcolo stili a runtime) e complica il SSR.
 *   Con Tailwind, gli stili sono statici nel CSS finale → zero runtime, compatibile
 *   con qualsiasi bundler/framework.
 *
 * `darkMode: ["class"]`:
 *   Il dark mode è attivato tramite la classe "dark" su <html> (aggiunta da useTheme).
 *   Alternativa: "media" usa prefers-color-scheme del sistema, ma non permette
 *   all'utente di scegliere manualmente. "class" + localStorage = pieno controllo.
 *
 * `content`:
 *   Tailwind analizza questi file per trovare le classi usate ed escludere le altre.
 *   Senza questa lista, il CSS generato includerebbe TUTTE le utility (~3MB).
 *   Con tree-shaking: ~10-50KB nel bundle di produzione.
 *
 * `theme.container`:
 *   Centra il contenuto con `mx-auto` + `padding: 1.5rem` (24px) e limita
 *   la larghezza a 1400px su schermi 2xl. Usato nel layout AppShell (`container`).
 *
 * Font `Fira Sans` e `Fira Code`:
 *   Fira Sans → testo UI (leggibilità ottimale per corpi piccoli).
 *   Fira Code → elementi monospaziati (filename, timestamp, badge). I caratteri
 *   sono caricati da Google Fonts (index.html). `ui-sans-serif` e `system-ui`
 *   sono fallback se Google Fonts non è disponibile (offline, privacy browser).
 *
 * Token colore HSL via CSS variable (`hsl(var(--primary))`):
 *   shadcn/ui definisce i colori come variabili CSS in src/index.css.
 *   Tailwind li legge tramite `hsl(var(--...))`. Questo approccio permette di
 *   cambiare l'intera palette (es. da blu a verde) modificando solo index.css,
 *   senza toccare il codice TSX. Il theme-toggle funziona aggiungendo/rimuovendo
 *   la classe `dark` su `<html>`, dove le variabili CSS vengono ridefinite.
 *
 * `borderRadius` derivato da `--radius` (CSS variable):
 *   Permette di cambiare il raggio globale dell'app da un unico punto (index.css).
 *
 * Keyframes `accordion-down/up`:
 *   Animazioni per il componente Accordion (Radix UI/shadcn). Usano
 *   `--radix-accordion-content-height` (variabile CSS iniettata da Radix a runtime
 *   per animare verso un'altezza sconosciuta a compile time).
 *
 * `tailwindcss-animate`:
 *   Plugin che aggiunge le classi `animate-*` per le transizioni Radix (enter/exit).
 */
import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  // Dark mode via classe CSS su <html> (controllato da useTheme + localStorage).
  darkMode: ["class"],
  // File analizzati per il tree-shaking delle utility non usate.
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      // 24px di padding laterale su tutti i container: consistente tra desktop e mobile.
      padding: "1.5rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      fontFamily: {
        // Fira Sans: font sans-serif per UI (leggibilità ottimale a corpo piccolo).
        sans: ["'Fira Sans'", "ui-sans-serif", "system-ui", "sans-serif"],
        // Fira Code: font monospaced per filename, timestamp, codice.
        mono: ["'Fira Code'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // Tutti i colori sono CSS variables HSL definiti in src/index.css (stile shadcn/ui).
        // Cambiarli in index.css cambia l'intera palette senza toccare il TSX.
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        // `--radius` in index.css: cambiarlo modifica i bordi di tutta l'app.
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        // Keyframes per il componente Accordion (Radix UI). `--radix-accordion-content-height`
        // è una CSS variable iniettata da Radix a runtime (altezza dinamica).
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  // tailwindcss-animate: aggiunge classi animate-* per le transizioni Radix.
  plugins: [animate],
} satisfies Config;
