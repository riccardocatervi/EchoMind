/**
 * Segnaposto della home protetta. Verra' sostituito dalla dashboard documenti
 * nel CP4. Serve solo a dimostrare che l'area autenticata e' raggiungibile.
 */
export function Home() {
  return (
    <div className="space-y-2">
      <h1 className="font-mono text-2xl font-semibold tracking-tight">I tuoi documenti</h1>
      <p className="text-muted-foreground">
        Sei autenticato. La dashboard dei documenti arriva nel prossimo checkpoint.
      </p>
    </div>
  );
}
