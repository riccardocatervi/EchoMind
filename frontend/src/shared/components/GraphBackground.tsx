import { useEffect, useRef } from "react";

import { cn } from "@/shared/lib/utils";

/**
 * Canvas full-viewport con una rete di nodi animata che reagisce al mouse.
 *
 * I nodi si muovono lentamente (moto browniano con smorzamento) e vengono
 * respinti dal cursore. Le connessioni tra nodi vicini diventano via via piu'
 * trasparenti con la distanza, evocando un grafo sparso.
 *
 * Posizionamento: `fixed inset-0 -z-10` --> dietro tutto il contenuto, senza
 * influenzare il layout. `pointer-events-none` --> non intercetta click/hover.
 */
export function GraphBackground({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    // Guard: il canvas non e' ancora montato.
    const canvasEl = canvasRef.current;
    if (!canvasEl) return;
    const ctxEl = canvasEl.getContext("2d");
    if (!ctxEl) return;

    // Rebind con tipo non-nullable: TypeScript non propaga il narrowing
    // di controllo-flusso nelle funzioni annidate (const narrowing), ma
    // inferisce il tipo della variabile dall'assegnazione.
    // Dopo i guard sopra, `canvasEl` e' HTMLCanvasElement, `ctxEl` e' ...2D.
    const canvas = canvasEl;
    const ctx = ctxEl;

    // --- Costanti ---
    const NODE_COUNT = 80;
    const LINE_DISTANCE = 140;
    const MOUSE_RADIUS = 130;
    const MOUSE_FORCE = 0.06;
    const BASE_SPEED = 0.3;
    const DAMPING = 0.984;
    const MIN_SPEED = 0.08;

    interface GraphNode {
      x: number;
      y: number;
      vx: number;
      vy: number;
    }

    let raf = 0;
    let w = 0;
    let h = 0;
    const mouse = { x: -9999, y: -9999 };
    let nodes: GraphNode[] = [];

    function init() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      nodes = Array.from({ length: NODE_COUNT }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * BASE_SPEED * 2,
        vy: (Math.random() - 0.5) * BASE_SPEED * 2,
      }));
    }

    function tick() {
      ctx.clearRect(0, 0, w, h);

      // 1. Aggiorna posizioni
      for (const n of nodes) {
        const dx = n.x - mouse.x;
        const dy = n.y - mouse.y;
        const dist2 = dx * dx + dy * dy;
        if (dist2 < MOUSE_RADIUS * MOUSE_RADIUS && dist2 > 0) {
          const dist = Math.sqrt(dist2);
          const f = ((MOUSE_RADIUS - dist) / MOUSE_RADIUS) * MOUSE_FORCE;
          n.vx += (dx / dist) * f;
          n.vy += (dy / dist) * f;
        }

        n.vx *= DAMPING;
        n.vy *= DAMPING;

        const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
        if (speed < MIN_SPEED) {
          n.vx += (Math.random() - 0.5) * MIN_SPEED * 0.8;
          n.vy += (Math.random() - 0.5) * MIN_SPEED * 0.8;
        }

        n.x += n.vx;
        n.y += n.vy;

        // Wrap-around: i nodi ricompaiono dall'altro lato
        if (n.x < 0) n.x += w;
        if (n.x > w) n.x -= w;
        if (n.y < 0) n.y += h;
        if (n.y > h) n.y -= h;
      }

      // 2. Archi (O(n^2) con ~55 nodi = ~1485 confronti/frame, trascurabile)
      ctx.lineWidth = 0.7;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < LINE_DISTANCE) {
            const alpha = (1 - dist / LINE_DISTANCE) * 0.22;
            ctx.strokeStyle = `rgba(99, 120, 220, ${alpha.toFixed(3)})`;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }

      // 3. Nodi
      for (const n of nodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(99, 120, 220, 0.55)";
        ctx.fill();
      }

      raf = requestAnimationFrame(tick);
    }

    const onMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    const onMouseLeave = () => {
      mouse.x = -9999;
      mouse.y = -9999;
    };
    const onVisibilityChange = () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
      } else {
        raf = requestAnimationFrame(tick);
      }
    };

    init();
    raf = requestAnimationFrame(tick);

    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("resize", init);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("resize", init);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={cn("pointer-events-none fixed inset-0 z-0", className)}
      aria-hidden="true"
    />
  );
}
