/**
 * TypewriterText — effetto macchina da scrivere con cancellazione e ridigitazione.
 *
 * Funzionamento:
 * 1. "Digita" la frase corrente carattere per carattere (TYPE_SPEED ms/char)
 * 2. Pausa (PAUSE_MS) a fine frase
 * 3. "Cancella" carattere per carattere (DELETE_SPEED ms/char, piu' veloce)
 * 4. Passa alla frase successiva (ciclo)
 *
 * Il cursore lampeggia tramite CSS (classe Tailwind `animate-pulse`).
 */
import { useEffect, useRef, useState } from "react";

interface TypewriterTextProps {
  phrases: string[];
  typeSpeed?: number; // ms per carattere in scrittura
  deleteSpeed?: number; // ms per carattere in cancellazione
  pauseMs?: number; // ms di pausa a fine frase prima di cancellare
  className?: string;
}

export function TypewriterText({
  phrases,
  typeSpeed = 55,
  deleteSpeed = 28,
  pauseMs = 1800,
  className,
}: TypewriterTextProps) {
  const [displayed, setDisplayed] = useState("");
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [phase, setPhase] = useState<"typing" | "pausing" | "deleting">("typing");

  // Ref per il timeout: gestisce correttamente il cleanup senza stale closure.
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (phrases.length === 0) return;

    const current = phrases[phraseIdx] ?? "";

    function schedule(fn: () => void, delay: number) {
      timerRef.current = setTimeout(fn, delay);
    }

    if (phase === "typing") {
      if (displayed.length < current.length) {
        schedule(() => {
          setDisplayed(current.slice(0, displayed.length + 1));
        }, typeSpeed);
      } else {
        // Frase completata: entra in pausa
        setPhase("pausing");
      }
    } else if (phase === "pausing") {
      schedule(() => setPhase("deleting"), pauseMs);
    } else {
      // phase === "deleting"
      if (displayed.length > 0) {
        schedule(() => {
          setDisplayed((prev) => prev.slice(0, -1));
        }, deleteSpeed);
      } else {
        // Cancellazione completata: passa alla frase successiva
        setPhraseIdx((i) => (i + 1) % phrases.length);
        setPhase("typing");
      }
    }

    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, [displayed, phase, phraseIdx, phrases, typeSpeed, deleteSpeed, pauseMs]);

  return (
    <span className={className}>
      {displayed}
      {/* Cursore lampeggiante: visibile anche quando displayed e' vuoto */}
      <span
        className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse bg-current align-middle"
        aria-hidden="true"
      />
    </span>
  );
}
