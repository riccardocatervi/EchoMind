import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/features/auth/AuthShell";
import { useAuth } from "@/features/auth/useAuth";

export function SignupPage() {
  const { status, signUp } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const { data, error: authError } = await signUp(email, password);
    setSubmitting(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    // Se la conferma email e' disattivata, Supabase ritorna gia' una sessione.
    if (data.session) {
      navigate("/", { replace: true });
      return;
    }
    setInfo("Registrazione ricevuta. Controlla la tua email per confermare l'account.");
  }

  return (
    <AuthShell title="EchoMind" description="Crea il tuo account">
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {info && (
          <p role="status" className="text-sm text-muted-foreground">
            {info}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
          Registrati
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        Hai gia' un account?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Accedi
        </Link>
      </p>
    </AuthShell>
  );
}
