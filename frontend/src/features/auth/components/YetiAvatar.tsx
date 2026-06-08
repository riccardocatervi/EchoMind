/**
 * YetiAvatar -- adattamento React del login SVG yeti di Darin Senneff.
 *
 * Animazioni GSAP (core free, senza MorphSVG):
 *   - coverEyes / uncoverEyes: braccia in 0.45 s / 1.35 s (Quad.easeOut).
 *   - spreadFingers / closeFingers: dita a 30 gradi in 0.35 s.
 *   - Lampeggio: scaleY(0) yoyo, delay 0-12 s, sospeso quando coperti.
 *   - calculateFaceMove: occhi, naso, bocca, mento, viso, orecchie, capelli
 *     seguono la posizione del cursore nel campo email (Expo.easeOut 1 s).
 *   - Bocca: tre stati (small / medium / large) cambio visibilita' React.
 *     small = nessun testo, medium = testo senza @, large = @ presente.
 *
 * Palette EchoMind (primary hsl(217 91% 60%)):
 *   #93c5fd blue-300  -- sfondo cerchio
 *   #dbeafe blue-100  -- viso / orecchie / braccia
 *   #1e3a8a blue-900  -- tutti i contorni
 *   #3b82f6 blue-500  -- bocca (primary EchoMind)
 *   #bfdbfe blue-200  -- unghie / accenti
 *   #db2777 pink-600  -- lingua
 *   #ffffff bianco    -- corpo / capelli / dente
 *
 * Fix show-password: PasswordInput deve chiamare e.preventDefault() nel suo
 * onMouseDown sull'occhio, cosi' il focus resta sull'input password e le
 * braccia non si abbassano prima che lo stato passwordVisible sia aggiornato.
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import gsap from "gsap";

import { cn } from "@/shared/lib/utils";

interface YetiAvatarProps {
  /** True quando il campo password (o il toggle) ha il focus. */
  passwordFocused: boolean;
  /** True quando la password e' visibile (toggle attivo). */
  passwordVisible: boolean;
  /** True quando il campo email ha il focus. */
  emailFocused?: boolean;
  /** Valore corrente del campo email (innesca face tracking). */
  emailValue?: string;
  /** Ref al DOM input email (per misurare posizione caret). */
  emailInputRef?: React.RefObject<HTMLInputElement | null>;
  className?: string;
}

type MouthState = "small" | "medium" | "large";

export function YetiAvatar({
  passwordFocused,
  passwordVisible,
  emailFocused = false,
  emailValue = "",
  emailInputRef,
  className,
}: YetiAvatarProps) {
  /* ---- ID univoci per i clipPath (evita collisioni multi-istanza) ---- */
  const uid = useId().replace(/:/g, "");
  const armMaskId = `am-${uid}`;
  const armMaskPathId = `amp-${uid}`;
  const mouthClipSmallId = `mcs-${uid}`;
  const mouthClipMediumId = `mcm-${uid}`;
  const mouthClipLargeId = `mcl-${uid}`;
  const mouthPathSmallId = `mps-${uid}`;
  const mouthPathMediumId = `mpm-${uid}`;
  const mouthPathLargeId = `mpl-${uid}`;

  /* ---- Stato bocca: cambia al variare del testo email ---- */
  const [mouthState, setMouthState] = useState<MouthState>("small");

  /* ---- Corpo: spalle dritte quando braccia alzate ---- */
  const bodyChanged = passwordFocused;

  /* ---- Refs ---- */
  const svgContainerRef = useRef<HTMLDivElement>(null);
  // Face elements
  const faceRef = useRef<SVGPathElement>(null);
  const eyeLRef = useRef<SVGGElement>(null);
  const eyeRRef = useRef<SVGGElement>(null);
  const noseRef = useRef<SVGPathElement>(null);
  const mouthGroupRef = useRef<SVGGElement>(null);
  const chinRef = useRef<SVGPathElement>(null);
  const eyebrowRef = useRef<SVGGElement>(null);
  const outerEarLRef = useRef<SVGGElement>(null);
  const outerEarRRef = useRef<SVGGElement>(null);
  const earHairLRef = useRef<SVGGElement>(null);
  const earHairRRef = useRef<SVGGElement>(null);
  const hairRef = useRef<SVGPathElement>(null);
  const toothRef = useRef<SVGPathElement>(null);
  const tongueRef = useRef<SVGGElement>(null);
  // Arm elements
  const armLRef = useRef<SVGGElement>(null);
  const armRRef = useRef<SVGGElement>(null);
  const twoFingersRef = useRef<SVGGElement>(null);
  // Timer blink + tween corrente (per fermare SOLO il lampeggio nel cleanup)
  const blinkTimerRef = useRef<number | undefined>(undefined);
  const blinkTweenRef = useRef<gsap.core.Tween | null>(null);

  /* ========================================================
     MOUNT: posiziona braccia fuori dal clip circle
     ======================================================== */
  useEffect(() => {
    const armL = armLRef.current;
    const armR = armRRef.current;
    if (!armL || !armR) return;
    gsap.set(armL, { x: -93, y: 220, rotation: 105, transformOrigin: "top left" });
    gsap.set(armR, { x: -93, y: 220, rotation: -105, transformOrigin: "top right" });
    return () => { gsap.killTweensOf([armL, armR]); };
  }, []);

  /* ========================================================
     BRACCIA / DITA: reagisce a passwordFocused / passwordVisible
     Matcha esattamente coverEyes(), uncoverEyes(), spreadFingers(),
     closeFingers() dell'originale (TweenMax --> gsap GSAP 3).
     ======================================================== */
  useEffect(() => {
    const armL = armLRef.current;
    const armR = armRRef.current;
    const tf = twoFingersRef.current;
    if (!armL || !armR || !tf) return;

    if (passwordFocused && !passwordVisible) {
      // coverEyes
      gsap.killTweensOf([armL, armR]);
      gsap.set([armL, armR], { visibility: "visible" });
      gsap.to(armL, { duration: 0.45, x: -93, y: 10, rotation: 0, ease: "power2.out" });
      gsap.to(armR, { duration: 0.45, x: -93, y: 10, rotation: 0, ease: "power2.out", delay: 0.1 });
      // closeFingers (nel caso fossero aperti)
      gsap.to(tf, { duration: 0.35, rotation: 0, x: 0, y: 0, ease: "power2.inOut" });
    } else if (passwordFocused && passwordVisible) {
      // spreadFingers (braccia gia' su, o si alzano mentre si apre)
      gsap.killTweensOf([armL, armR, tf]);
      gsap.set([armL, armR], { visibility: "visible" });
      gsap.to(armL, { duration: 1, y: 10, ease: "power2.out" });
      gsap.to(armR, { duration: 1, y: 10, ease: "power2.out", delay: 0.1 });
      gsap.to(tf, {
        duration: 0.35,
        transformOrigin: "bottom left",
        rotation: 30,
        x: -9,
        y: -2,
        ease: "power2.inOut",
      });
    } else {
      // uncoverEyes
      gsap.killTweensOf([armL, armR, tf]);
      gsap.to(tf, { duration: 0.35, rotation: 0, x: 0, y: 0, ease: "power2.inOut" });
      gsap.to(armL, { duration: 1.35, y: 220, ease: "power2.out" });
      gsap.to(armL, { duration: 1.35, rotation: 105, ease: "power2.out", delay: 0.1 });
      gsap.to(armR, { duration: 1.35, y: 220, ease: "power2.out" });
      gsap.to(armR, {
        duration: 1.35,
        rotation: -105,
        ease: "power2.out",
        delay: 0.1,
        onComplete: () => gsap.set([armL, armR], { visibility: "hidden" }),
      });
    }
  }, [passwordFocused, passwordVisible]);

  /* ========================================================
     LAMPEGGIO CASUALE: sospeso quando braccia coprono gli occhi
     ======================================================== */
  useEffect(() => {
    const covering = passwordFocused && !passwordVisible;
    const eyeL = eyeLRef.current;
    const eyeR = eyeRRef.current;
    if (covering || !eyeL || !eyeR) {
      window.clearTimeout(blinkTimerRef.current);
      return;
    }

    // Delay 0-12 s come getRandomInt(12) nell'originale; prima chiamata 1 s fisso.
    const scheduleBlink = (firstCall = false) => {
      const delay = firstCall ? 1000 : Math.floor(Math.random() * 12000);
      blinkTimerRef.current = window.setTimeout(() => {
        // Salviamo il tween del lampeggio in un ref: il cleanup deve fermare
        // SOLO questo (scaleY), non tutti i tween degli occhi. Prima usava
        // gsap.killTweensOf([eyeL, eyeR]) che uccideva anche il tween di reset
        // x/y avviato da resetFace() al blur dell'email -> occhi "bloccati a
        // destra" passando al campo password.
        blinkTweenRef.current = gsap.to([eyeL, eyeR], {
          duration: 0.1,
          scaleY: 0,
          yoyo: true,
          repeat: 1,
          transformOrigin: "center center",
          onComplete: () => scheduleBlink(),
        });
      }, delay);
    };

    scheduleBlink(true);
    return () => {
      window.clearTimeout(blinkTimerRef.current);
      blinkTweenRef.current?.kill();
      blinkTweenRef.current = null;
      // Ripristina l'apertura degli occhi se il cleanup interrompe un blink.
      gsap.set([eyeL, eyeR], { scaleY: 1 });
    };
  }, [passwordFocused, passwordVisible]);

  /* ========================================================
     RESET FACCIA: riporta tutti gli elementi alla posizione zero
     ======================================================== */
  const resetFace = useCallback(() => {
    const all = [
      eyeLRef.current, eyeRRef.current,
      noseRef.current,
      mouthGroupRef.current,
      chinRef.current,
      faceRef.current, eyebrowRef.current,
      outerEarLRef.current, outerEarRRef.current,
      earHairLRef.current, earHairRRef.current,
      hairRef.current,
    ].filter(Boolean);

    gsap.to([eyeLRef.current, eyeRRef.current], { duration: 1, x: 0, y: 0, ease: "expo.out" });
    gsap.to(noseRef.current, { duration: 1, x: 0, y: 0, scaleX: 1, scaleY: 1, ease: "expo.out" });
    gsap.to(mouthGroupRef.current, { duration: 1, x: 0, y: 0, rotation: 0, ease: "expo.out" });
    gsap.to(chinRef.current, { duration: 1, x: 0, y: 0, scaleY: 1, ease: "expo.out" });
    gsap.to([faceRef.current, eyebrowRef.current], { duration: 1, x: 0, y: 0, skewX: 0, ease: "expo.out" });
    gsap.to(
      [outerEarLRef.current, outerEarRRef.current, earHairLRef.current, earHairRRef.current, hairRef.current],
      { duration: 1, x: 0, y: 0, scaleY: 1, ease: "expo.out" },
    );
    // Evita memory leak: non usiamo `all` nel cleanup (e' solo per chiarezza)
    void all;
  }, []);

  /* ========================================================
     FACE TRACKING EMAIL
     Replica calculateFaceMove() + onEmailInput() dell'originale.
     Si attiva al cambio di emailFocused / emailValue.
     ======================================================== */
  useEffect(() => {
    if (!emailFocused) {
      // Blur email: ripristina faccia e bocca
      resetFace();
      setMouthState("small");
      gsap.to([eyeLRef.current, eyeRRef.current], {
        duration: 1, scaleX: 1, scaleY: 1, ease: "expo.out",
      });
      gsap.to(toothRef.current, { duration: 1, x: 0, y: 0, ease: "expo.out" });
      gsap.to(tongueRef.current, { duration: 1, x: 0, y: 0, ease: "expo.out" });
      return;
    }

    /* -- Aggiorna stato bocca (onEmailInput) -- */
    const value = emailValue;
    if (value.length === 0) {
      setMouthState("small");
      gsap.to([eyeLRef.current, eyeRRef.current], { duration: 1, scaleX: 1, scaleY: 1, ease: "expo.out" });
      gsap.to(toothRef.current, { duration: 1, x: 0, y: 0, ease: "expo.out" });
      gsap.to(tongueRef.current, { duration: 1, x: 0, y: 0, ease: "expo.out" });
    } else if (value.includes("@")) {
      setMouthState("large");
      gsap.to([eyeLRef.current, eyeRRef.current], {
        duration: 1, scaleX: 0.65, scaleY: 0.65,
        transformOrigin: "center center", ease: "expo.out",
      });
      gsap.to(toothRef.current, { duration: 1, x: 3, y: -2, ease: "expo.out" });
      gsap.to(tongueRef.current, { duration: 1, y: 2, ease: "expo.out" });
    } else {
      setMouthState("medium");
      gsap.to([eyeLRef.current, eyeRRef.current], { duration: 1, scaleX: 0.85, scaleY: 0.85, ease: "expo.out" });
      gsap.to(toothRef.current, { duration: 1, x: 0, y: 0, ease: "expo.out" });
      gsap.to(tongueRef.current, { duration: 1, x: 0, y: 1, ease: "expo.out" });
    }

    /* -- calculateFaceMove: segue il caret nell'input email -- */
    const input = emailInputRef?.current;
    const container = svgContainerRef.current;
    if (!input || !container) return;

    const svgRect = container.getBoundingClientRect();
    const inputRect = input.getBoundingClientRect();
    const svgPx = svgRect.width; // larghezza SVG in px CSS
    const scale = svgPx / 200; // fattore viewBox (200) --> px display

    // Centro SVG in coordinate viewport
    const screenCenter = svgRect.left + svgPx / 2;

    // --- Posizione REALE del caret nell'input ---------------------------
    // L'originale misura la larghezza del testo digitato (mirror div). Qui
    // usiamo canvas.measureText col font calcolato dell'input. La vecchia
    // versione approssimava con carPos/lunghezza * larghezza_input: scrivendo
    // in fondo il rapporto era sempre 1 -> il caret finiva sul bordo destro e
    // lo yeti guardava subito a destra invece di seguire la lettera.
    const carPos = input.selectionEnd ?? input.value.length;
    const style = getComputedStyle(input);
    let textWidth = 0;
    const ctx = document.createElement("canvas").getContext("2d");
    if (ctx) {
      ctx.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      textWidth = ctx.measureText(input.value.substring(0, carPos)).width;
    }
    const padLeft = parseFloat(style.paddingLeft) || 0;
    const padRight = parseFloat(style.paddingRight) || 0;
    let caretX = inputRect.left + padLeft + textWidth - input.scrollLeft;
    // Limita il caret all'area visibile dell'input (gestisce lo scroll).
    const caretMax = inputRect.right - padRight;
    if (caretX > caretMax) caretX = caretMax;
    if (caretX < inputRect.left + padLeft) caretX = inputRect.left + padLeft;
    const caretY = inputRect.top + inputRect.height / 2; // centro verticale input

    // dFromC riportato alla scala viewBox (originale: avatar 1px == 1 unita').
    const dFromC = (screenCenter - caretX) / scale;

    // Coordinate SVG degli elementi in spazio DOM (SVGcoord * scale + origine)
    const eyeLX_dom = svgRect.left + 84 * scale;
    const eyeLY_dom = svgRect.top + 76 * scale;
    const eyeRX_dom = svgRect.left + 113 * scale;
    const eyeRY_dom = svgRect.top + 76 * scale;
    const noseX_dom = svgRect.left + 97 * scale;
    const noseY_dom = svgRect.top + 81 * scale;
    const mouthX_dom = svgRect.left + 100 * scale;
    const mouthY_dom = svgRect.top + 100 * scale;

    // Angoli verso il caret
    const eyeLAngle = Math.atan2(eyeLY_dom - caretY, eyeLX_dom - caretX);
    const eyeRAngle = Math.atan2(eyeRY_dom - caretY, eyeRX_dom - caretX);
    const noseAngle = Math.atan2(noseY_dom - caretY, noseX_dom - caretX);
    const mouthAngle = Math.atan2(mouthY_dom - caretY, mouthX_dom - caretX);

    // Spostamenti in UNITA' viewBox -- i fattori 20/10/23/6 sono quelli
    // originali. GSAP applica x/y nello spazio utente dell'SVG, quindi NON
    // vanno moltiplicati per `scale` (lo facevamo prima e i movimenti
    // risultavano troppo piccoli).
    const eLX = Math.cos(eyeLAngle) * 20;
    const eLY = Math.sin(eyeLAngle) * 10;
    const eRX = Math.cos(eyeRAngle) * 20;
    const eRY = Math.sin(eyeRAngle) * 10;
    const nX  = Math.cos(noseAngle)  * 23;
    const nY  = Math.sin(noseAngle)  * 10;
    const mX  = Math.cos(mouthAngle) * 23;
    const mY  = Math.sin(mouthAngle) * 10;
    const mR  = Math.cos(mouthAngle) * 6; // gradi
    const cX  = mX * 0.8;
    const cY  = mY * 0.5;
    let   cS  = 1 - (dFromC * 0.15) / 100;
    if (cS > 1) { cS = 1 - (cS - 1); if (cS < 0.5) cS = 0.5; }
    const fX  = mX * 0.3;
    const fY  = mY * 0.4;
    const fSk = Math.cos(mouthAngle) * 5;  // gradi
    const eSk = Math.cos(mouthAngle) * 25; // gradi
    const eaX = Math.cos(mouthAngle) * 4;
    const eaY = Math.cos(mouthAngle) * 5;
    const hX  = Math.cos(mouthAngle) * 6;

    const dur = { duration: 1, ease: "expo.out" };

    gsap.to(eyeLRef.current, { ...dur, x: -eLX, y: -eLY });
    gsap.to(eyeRRef.current, { ...dur, x: -eRX, y: -eRY });
    gsap.to(noseRef.current, { ...dur, x: -nX, y: -nY, rotation: mR, transformOrigin: "center center" });
    gsap.to(mouthGroupRef.current, { ...dur, x: -mX, y: -mY, rotation: mR, transformOrigin: "center center" });
    gsap.to(chinRef.current, { ...dur, x: -cX, y: -cY, scaleY: cS });
    gsap.to(faceRef.current, { ...dur, x: -fX, y: -fY, skewX: -fSk, transformOrigin: "center top" });
    gsap.to(eyebrowRef.current, { ...dur, x: -fX, y: -fY, skewX: -eSk, transformOrigin: "center top" });
    gsap.to(outerEarLRef.current, { ...dur, x:  eaX, y: -eaY });
    gsap.to(outerEarRRef.current, { ...dur, x:  eaX, y:  eaY });
    gsap.to(earHairLRef.current,  { ...dur, x: -eaX, y: -eaY });
    gsap.to(earHairRRef.current,  { ...dur, x: -eaX, y:  eaY });
    gsap.to(hairRef.current, { ...dur, x: hX, scaleY: 1.2, transformOrigin: "center bottom" });
  }, [emailFocused, emailValue, emailInputRef, resetFace]);

  /* ---- clip attivo per lingua/dente: deve seguire la forma della bocca ----
     Prima lo stato "medium" riusava il clip della bocca piccola (una fessura
     chiusa): lingua e dente venivano ritagliati via e si vedeva solo l'azzurro
     della bocca. Ora ogni stato ha il proprio clip. */
  const activeMouthClip = `url(#${
    mouthState === "large"
      ? mouthClipLargeId
      : mouthState === "medium"
        ? mouthClipMediumId
        : mouthClipSmallId
  })`;

  /* ================================================================
     SVG
     ================================================================ */
  return (
    /*
     * overflow-hidden: taglia il cerchio SVG in modo preciso.
     * ring: bordo circolare sovrapposto (matcha il ::after del CSS originale).
     */
    <div
      ref={svgContainerRef}
      className={cn(
        "relative overflow-hidden rounded-full ring-[2.5px] ring-[#1e3a8a]/70",
        className,
      )}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 200 200"
        className="h-full w-full"
        aria-hidden="true"
      >
        {/* ---- Arm clip (cerchio = viewBox) ---- */}
        <defs>
          <circle id={armMaskPathId} cx="100" cy="100" r="100" />
          <clipPath id={armMaskId}>
            <use href={`#${armMaskPathId}`} overflow="visible" />
          </clipPath>
        </defs>

        {/* ---- Sfondo cerchio ---- */}
        <circle cx="100" cy="100" r="100" fill="#93c5fd" />

        {/* ----------------------------------------------------------------
            Corpo
            ---------------------------------------------------------------- */}
        <g>
          {/* Spalle dritte -- braccia alzate.
              Nell'originale il corpo veniva "morphato" (morphSVG) mantenendo
              lo stesso stroke: qui sono due path distinti, quindi questo deve
              avere lo stesso contorno blu, altrimenti sparisce passando alla
              password. */}
          <path
            style={{ display: bodyChanged ? "block" : "none" }}
            fill="#ffffff"
            stroke="#1e3a8a"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M200,122h-35h-14.9V72c0-27.6-22.4-50-50-50s-50,22.4-50,50v50H35.8H0l0,91h200L200,122z"
          />
          {/* Corpo normale */}
          <path
            style={{ display: bodyChanged ? "none" : "block" }}
            stroke="#1e3a8a"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="#ffffff"
            d="M200,158.5c0-20.2-14.8-36.5-35-36.5h-14.9V72.8
               c0-27.4-21.7-50.4-49.1-50.8c-28-0.5-50.9,22.1-50.9,50v50
               H35.8C16,122,0,138,0,157.8L0,213h200L200,158.5z"
          />
          {/* Colletto */}
          <path
            fill="#dbeafe"
            d="M100,156.4c-22.9,0-43,11.1-54.1,27.7
               c15.6,10,34.2,15.9,54.1,15.9s38.5-5.8,54.1-15.9
               C143,167.5,122.9,156.4,100,156.4z"
          />
        </g>

        {/* ----------------------------------------------------------------
            Orecchio sinistro
            ---------------------------------------------------------------- */}
        <g>
          <g ref={outerEarLRef} fill="#dbeafe" stroke="#1e3a8a" strokeWidth="2.5">
            <circle cx="47" cy="83" r="11.5" />
            <path
              d="M46.3 78.9c-2.3 0-4.1 1.9-4.1 4.1 0 2.3 1.9 4.1 4.1 4.1"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </g>
          <g ref={earHairLRef}>
            <rect x="51" y="64" fill="#ffffff" width="15" height="35" />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M53.4 62.8C48.5 67.4 45 72.2 42.8 77c3.4-.1 6.8-.1 10.1.1
                 -4 3.7-6.8 7.6-8.2 11.6 2.1 0 4.2 0 6.3.2
                 -2.6 4.1-3.8 8.3-3.7 12.5 1.2-.7 3.4-1.4 5.2-1.9"
            />
          </g>
        </g>

        {/* ----------------------------------------------------------------
            Orecchio destro
            ---------------------------------------------------------------- */}
        <g>
          <g ref={outerEarRRef}>
            <circle fill="#dbeafe" stroke="#1e3a8a" strokeWidth="2.5" cx="153" cy="83" r="11.5" />
            <path
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M153.7,78.9c2.3,0,4.1,1.9,4.1,4.1c0,2.3-1.9,4.1-4.1,4.1"
            />
          </g>
          <g ref={earHairRRef}>
            <rect x="134" y="64" fill="#ffffff" width="15" height="35" />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M146.6,62.8c4.9,4.6,8.4,9.4,10.6,14.2c-3.4-0.1-6.8-0.1-10.1,0.1
                 c4,3.7,6.8,7.6,8.2,11.6c-2.1,0-4.2,0-6.3,0.2
                 c2.6,4.1,3.8,8.3,3.7,12.5c-1.2-0.7-3.4-1.4-5.2-1.9"
            />
          </g>
        </g>

        {/* Mento */}
        <path
          ref={chinRef}
          fill="none"
          stroke="#1e3a8a"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M84.1 121.6c2.7 2.9 6.1 5.4 9.8 7.5l.9-4.5
             c2.9 2.5 6.3 4.8 10.2 6.5 0-1.9-.1-3.9-.2-5.8
             3 1.2 6.2 2 9.7 2.5-.3-2.1-.7-4.1-1.2-6.1"
        />

        {/* Viso (base azzurra) */}
        <path
          ref={faceRef}
          fill="#dbeafe"
          d="M134.5,46v35.5c0,21.815-15.446,39.5-34.5,39.5s-34.5-17.685-34.5-39.5V46"
        />

        {/* Capelli */}
        <path
          ref={hairRef}
          fill="#ffffff"
          stroke="#1e3a8a"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M81.457,27.929c1.755-4.084,5.51-8.262,11.253-11.77
             c0.979,2.565,1.883,5.14,2.712,7.723
             c3.162-4.265,8.626-8.27,16.272-11.235
             c-0.737,3.293-1.588,6.573-2.554,9.837
             c4.857-2.116,11.049-3.64,18.428-4.156
             c-2.403,3.23-5.021,6.391-7.852,9.474"
        />

        {/* Sopracciglio */}
        <g ref={eyebrowRef}>
          <path
            fill="#ffffff"
            d="M138.142,55.064c-4.93,1.259-9.874,2.118-14.787,2.599
               c-0.336,3.341-0.776,6.689-1.322,10.037
               c-4.569-1.465-8.909-3.222-12.996-5.226
               c-0.98,3.075-2.07,6.137-3.267,9.179
               c-5.514-3.067-10.559-6.545-15.097-10.329
               c-1.806,2.889-3.745,5.73-5.816,8.515
               c-7.916-4.124-15.053-9.114-21.296-14.738l1.107-11.768h73.475V55.064z"
          />
          <path
            fill="#ffffff"
            stroke="#1e3a8a"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M63.56,55.102c6.243,5.624,13.38,10.614,21.296,14.738
               c2.071-2.785,4.01-5.626,5.816-8.515
               c4.537,3.785,9.583,7.263,15.097,10.329
               c1.197-3.043,2.287-6.104,3.267-9.179
               c4.087,2.004,8.427,3.761,12.996,5.226
               c0.545-3.348,0.986-6.696,1.322-10.037
               c4.913-0.481,9.857-1.34,14.787-2.599"
          />
        </g>

        {/* Occhio sinistro */}
        <g ref={eyeLRef}>
          <circle cx="85.5" cy="78.5" r="3.5" fill="#1e3a8a" />
          <circle cx="84" cy="76" r="1" fill="#fff" />
        </g>

        {/* Occhio destro */}
        <g ref={eyeRRef}>
          <circle cx="114.5" cy="78.5" r="3.5" fill="#1e3a8a" />
          <circle cx="113" cy="76" r="1" fill="#fff" />
        </g>

        {/* ----------------------------------------------------------------
            Bocca (il gruppo si muove per il face tracking)
            Tre stati: small (riposo) / medium (testo) / large (@ presente).
            I path small e large fanno anche da definizione dei due clipPath
            per ritagliare lingua e dente in modo corretto.
            ---------------------------------------------------------------- */}
        <g ref={mouthGroupRef}>
          {/* Definizioni locali al gruppo: si muovono con esso */}
          <defs>
            <path
              id={mouthPathSmallId}
              d="M100.2,101c-0.4,0-1.4,0-1.8,0c-2.7-0.3-5.3-1.1-8-2.5
                 c-0.7-0.3-0.9-1.2-0.6-1.8c0.2-0.5,0.7-0.7,1.2-0.7
                 c0.2,0,0.5,0.1,0.6,0.2c3,1.5,5.8,2.3,8.6,2.3s5.7-0.7,8.6-2.3
                 c0.2-0.1,0.4-0.2,0.6-0.2c0.5,0,1,0.3,1.2,0.7
                 c0.4,0.7,0.1,1.5-0.6,1.9c-2.6,1.4-5.3,2.2-7.9,2.5
                 C101.7,101,100.5,101,100.2,101z"
            />
            <path
              id={mouthPathLargeId}
              d="M100 110.2c-9 0-16.2-7.3-16.2-16.2
                 0-2.3 1.9-4.2 4.2-4.2h24c2.3 0 4.2 1.9 4.2 4.2
                 0 9-7.2 16.2-16.2 16.2z"
            />
            <path
              id={mouthPathMediumId}
              d="M95,104.2c-4.5,0-8.2-3.7-8.2-8.2v-2c0-1.2,1-2.2,2.2-2.2
                 h22c1.2,0,2.2,1,2.2,2.2v2c0,4.5-3.7,8.2-8.2,8.2H95z"
            />
            <clipPath id={mouthClipSmallId}>
              <use href={`#${mouthPathSmallId}`} overflow="visible" />
            </clipPath>
            <clipPath id={mouthClipMediumId}>
              <use href={`#${mouthPathMediumId}`} overflow="visible" />
            </clipPath>
            <clipPath id={mouthClipLargeId}>
              <use href={`#${mouthPathLargeId}`} overflow="visible" />
            </clipPath>
          </defs>

          {/* Riempimento bocca piccola (riposo) */}
          <path
            style={{ display: mouthState === "small" ? "block" : "none" }}
            fill="#3b82f6"
            d="M100.2,101c-0.4,0-1.4,0-1.8,0c-2.7-0.3-5.3-1.1-8-2.5
               c-0.7-0.3-0.9-1.2-0.6-1.8c0.2-0.5,0.7-0.7,1.2-0.7
               c0.2,0,0.5,0.1,0.6,0.2c3,1.5,5.8,2.3,8.6,2.3s5.7-0.7,8.6-2.3
               c0.2-0.1,0.4-0.2,0.6-0.2c0.5,0,1,0.3,1.2,0.7
               c0.4,0.7,0.1,1.5-0.6,1.9c-2.6,1.4-5.3,2.2-7.9,2.5
               C101.7,101,100.5,101,100.2,101z"
          />

          {/* Bocca media (testo senza @) */}
          <path
            style={{ display: mouthState === "medium" ? "block" : "none" }}
            fill="#3b82f6"
            stroke="#1e3a8a"
            strokeWidth="2"
            strokeLinejoin="round"
            d="M95,104.2c-4.5,0-8.2-3.7-8.2-8.2v-2c0-1.2,1-2.2,2.2-2.2
               h22c1.2,0,2.2,1,2.2,2.2v2c0,4.5-3.7,8.2-8.2,8.2H95z"
          />

          {/* Bocca grande (@ presente, sorriso ampio) */}
          <path
            style={{ display: mouthState === "large" ? "block" : "none" }}
            fill="#3b82f6"
            stroke="#1e3a8a"
            strokeWidth="2.5"
            strokeLinejoin="round"
            d="M100 110.2c-9 0-16.2-7.3-16.2-16.2
               0-2.3 1.9-4.2 4.2-4.2h24c2.3 0 4.2 1.9 4.2 4.2
               0 9-7.2 16.2-16.2 16.2z"
          />

          {/* Lingua (clip al contorno bocca attivo) */}
          <g clipPath={activeMouthClip}>
            <g ref={tongueRef}>
              <circle cx="100" cy="107" r="8" fill="#db2777" />
              <ellipse cx="100" cy="100.5" rx="3" ry="1.5" opacity=".1" fill="#fff" />
            </g>
          </g>

          {/* Dente (clip al contorno bocca attivo) */}
          <path
            ref={toothRef}
            clipPath={activeMouthClip}
            fill="#ffffff"
            d="M106,97h-4c-1.1,0-2-0.9-2-2v-2h8v2C108,96.1,107.1,97,106,97z"
          />

          {/* Contorno bocca (solo in stato small) */}
          <path
            style={{ display: mouthState === "small" ? "block" : "none" }}
            fill="none"
            stroke="#1e3a8a"
            strokeWidth="2.5"
            strokeLinejoin="round"
            d="M100.2,101c-0.4,0-1.4,0-1.8,0c-2.7-0.3-5.3-1.1-8-2.5
               c-0.7-0.3-0.9-1.2-0.6-1.8c0.2-0.5,0.7-0.7,1.2-0.7
               c0.2,0,0.5,0.1,0.6,0.2c3,1.5,5.8,2.3,8.6,2.3s5.7-0.7,8.6-2.3
               c0.2-0.1,0.4-0.2,0.6-0.2c0.5,0,1,0.3,1.2,0.7
               c0.4,0.7,0.1,1.5-0.6,1.9c-2.6,1.4-5.3,2.2-7.9,2.5
               C101.7,101,100.5,101,100.2,101z"
          />
        </g>

        {/* Naso */}
        <path
          ref={noseRef}
          fill="#1e3a8a"
          d="M97.7 79.9h4.7c1.9 0 3 2.2 1.9 3.7l-2.3 3.3c-.9 1.3-2.9 1.3-3.8 0
             l-2.3-3.3c-1.3-1.6-.2-3.7 1.8-3.7z"
        />

        {/* ----------------------------------------------------------------
            Braccia (clip al cerchio, animate da GSAP)
            ---------------------------------------------------------------- */}
        <g clipPath={`url(#${armMaskId})`}>
          {/* ---- Braccio sinistro ---- */}
          <g ref={armLRef} style={{ visibility: "hidden" }}>
            <polygon
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeMiterlimit={10}
              points="121.3,98.4 111,59.7 149.8,49.3 169.8,85.4"
            />
            <path
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeMiterlimit={10}
              d="M134.4,53.5l19.3-5.2c2.7-0.7,5.4,0.9,6.1,3.5v0
                 c0.7,2.7-0.9,5.4-3.5,6.1l-10.3,2.8"
            />
            <path
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeMiterlimit={10}
              d="M150.9,59.4l26-7c2.7-0.7,5.4,0.9,6.1,3.5v0
                 c0.7,2.7-0.9,5.4-3.5,6.1l-21.3,5.7"
            />
            {/* Due dita */}
            <g ref={twoFingersRef}>
              <path
                fill="#dbeafe"
                stroke="#1e3a8a"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeMiterlimit={10}
                d="M158.3,67.8l23.1-6.2c2.7-0.7,5.4,0.9,6.1,3.5v0
                   c0.7,2.7-0.9,5.4-3.5,6.1l-23.1,6.2"
              />
              <path
                fill="#bfdbfe"
                d="M180.1,65l2.2-0.6c1.1-0.3,2.2,0.3,2.4,1.4v0
                   c0.3,1.1-0.3,2.2-1.4,2.4l-2.2,0.6L180.1,65z"
              />
              <path
                fill="#dbeafe"
                stroke="#1e3a8a"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeMiterlimit={10}
                d="M160.8,77.5l19.4-5.2c2.7-0.7,5.4,0.9,6.1,3.5v0
                   c0.7,2.7-0.9,5.4-3.5,6.1l-18.3,4.9"
              />
              <path
                fill="#bfdbfe"
                d="M178.8,75.7l2.2-0.6c1.1-0.3,2.2,0.3,2.4,1.4v0
                   c0.3,1.1-0.3,2.2-1.4,2.4l-2.2,0.6L178.8,75.7z"
              />
            </g>
            <path
              fill="#bfdbfe"
              d="M175.5,55.9l2.2-0.6c1.1-0.3,2.2,0.3,2.4,1.4v0
                 c0.3,1.1-0.3,2.2-1.4,2.4l-2.2,0.6L175.5,55.9z"
            />
            <path
              fill="#bfdbfe"
              d="M152.1,50.4l2.2-0.6c1.1-0.3,2.2,0.3,2.4,1.4v0
                 c0.3,1.1-0.3,2.2-1.4,2.4l-2.2,0.6L152.1,50.4z"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M123.5,97.8c-41.4,14.9-84.1,30.7-108.2,35.5L1.2,81
                 c33.5-9.9,71.9-16.5,111.9-21.8"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M108.5,60.4c7.7-5.3,14.3-8.4,22.8-13.2
                 c-2.4,5.3-4.7,10.3-6.7,15.1c4.3,0.3,8.4,0.7,12.3,1.3
                 c-4.2,5-8.1,9.6-11.5,13.9c3.1,1.1,6,2.4,8.7,3.8
                 c-1.4,2.9-2.7,5.8-3.9,8.5c2.5,3.5,4.6,7.2,6.3,11
                 c-4.9-0.8-9-0.7-16.2-2.7"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M94.5,103.8c-0.6,4-3.8,8.9-9.4,14.7
                 c-2.6-1.8-5-3.7-7.2-5.7c-2.5,4.1-6.6,8.8-12.2,14
                 c-1.9-2.2-3.4-4.5-4.5-6.9c-4.4,3.3-9.5,6.9-15.4,10.8
                 c-0.2-3.4,0.1-7.1,1.1-10.9"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M97.5,63.9c-1.7-2.4-5.9-4.1-12.4-5.2
                 c-0.9,2.2-1.8,4.3-2.5,6.5c-3.8-1.8-9.4-3.1-17-3.8
                 c0.5,2.3,1.2,4.5,1.9,6.8c-5-0.6-11.2-0.9-18.4-1
                 c2,2.9,0.9,3.5,3.9,6.2"
            />
          </g>

          {/* ---- Braccio destro ---- */}
          <g ref={armRRef} style={{ visibility: "hidden" }}>
            <path
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeMiterlimit={10}
              strokeWidth="2.5"
              d="M265.4 97.3l10.4-38.6-38.9-10.5-20 36.1z"
            />
            <path
              fill="#dbeafe"
              stroke="#1e3a8a"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeMiterlimit={10}
              strokeWidth="2.5"
              d="M252.4 52.4L233 47.2c-2.7-.7-5.4.9-6.1 3.5-.7 2.7.9 5.4 3.5 6.1l10.3 2.8
                 M226 76.4l-19.4-5.2c-2.7-.7-5.4.9-6.1 3.5-.7 2.7.9 5.4 3.5 6.1l18.3 4.9
                 M228.4 66.7l-23.1-6.2c-2.7-.7-5.4.9-6.1 3.5-.7 2.7.9 5.4 3.5 6.1l23.1 6.2
                 M235.8 58.3l-26-7c-2.7-.7-5.4.9-6.1 3.5-.7 2.7.9 5.4 3.5 6.1l21.3 5.7"
            />
            <path
              fill="#bfdbfe"
              d="M207.9 74.7l-2.2-.6c-1.1-.3-2.2.3-2.4 1.4-.3 1.1.3 2.2 1.4 2.4l2.2.6 1-3.8z
                 M206.7 64l-2.2-.6c-1.1-.3-2.2.3-2.4 1.4-.3 1.1.3 2.2 1.4 2.4l2.2.6 1-3.8z
                 M211.2 54.8l-2.2-.6c-1.1-.3-2.2.3-2.4 1.4-.3 1.1.3 2.2 1.4 2.4l2.2.6 1-3.8z
                 M234.6 49.4l-2.2-.6c-1.1-.3-2.2.3-2.4 1.4-.3 1.1.3 2.2 1.4 2.4l2.2.6 1-3.8z"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2.5"
              d="M263.3 96.7c41.4 14.9 84.1 30.7 108.2 35.5l14-52.3C352 70 313.6 63.5 273.6 58.1"
            />
            <path
              fill="#ffffff"
              stroke="#1e3a8a"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2.5"
              d="M278.2 59.3l-18.6-10 2.5 11.9-10.7 6.5 9.9 8.7-13.9 6.4 9.1 5.9-13.2 9.2 23.1-.9
                 M284.5 100.1c-.4 4 1.8 8.9 6.7 14.8 3.5-1.8 6.7-3.6 9.7-5.5
                 1.8 4.2 5.1 8.9 10.1 14.1 2.7-2.1 5.1-4.4 7.1-6.8
                 4.1 3.4 9 7 14.7 11 1.2-3.4 1.8-7 1.7-10.9
                 M314 66.7s5.4-5.7 12.6-7.4c1.7 2.9 3.3 5.7 4.9 8.6
                 3.8-2.5 9.8-4.4 18.2-5.7.1 3.1.1 6.1 0 9.2
                 5.5-1 12.5-1.6 20.8-1.9-1.4 3.9-2.5 8.4-2.5 8.4"
            />
          </g>
        </g>
      </svg>
    </div>
  );
}
