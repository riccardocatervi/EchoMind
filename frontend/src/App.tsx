import { Network } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";

function App() {
  return (
    <AppShell>
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <Network className="size-10 text-primary" aria-hidden="true" />
        <h1 className="font-mono text-3xl font-semibold tracking-tight">EchoMind</h1>
        <p className="max-w-md text-balance text-muted-foreground">
          Scaffold pronto. Da qui costruiremo autenticazione, upload, riassunti e il visualizzatore
          del grafo di conoscenza.
        </p>
        <Button>Pronti per M6</Button>
      </div>
    </AppShell>
  );
}

export default App;
