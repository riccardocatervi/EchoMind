import type { ReactNode } from "react";
import { Network } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
}

/** Layout centrato per le pagine di autenticazione (login/signup). */
export function AuthShell({ title, description, children }: AuthShellProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-3 text-center">
          <div className="flex justify-center">
            <Network className="size-8 text-primary" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <CardTitle className="font-mono text-2xl">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  );
}
