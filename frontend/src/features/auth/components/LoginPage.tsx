import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { AuthShell } from "@/features/auth/components/AuthShell";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { credentialsSchema } from "@/features/auth/schemas/authSchema";

export function LoginPage() {
  const { t } = useTranslation();
  const { status, signInWithPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Ref al <form> per il submit programmatico su Enter.
  // Il Button component ora defaulta a type="button" (fix corretto), ma
  // aggiungiamo anche il handler esplicito per massima compatibilita'
  // con browser/password-manager che intercettano il keydown.
  const formRef = useRef<HTMLFormElement>(null);

  if (status === "authenticated") return <Navigate to="/documents" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const parsed = credentialsSchema.safeParse({ email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    setSubmitting(true);
    const { error: authError } = await signInWithPassword(parsed.data.email, parsed.data.password);
    setSubmitting(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    navigate("/documents", { replace: true });
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <AuthShell title={t("auth.login.title")} description={t("auth.login.description")}>
      <form
        ref={formRef}
        onSubmit={(event) => void handleSubmit(event)}
        className="space-y-4"
        noValidate
      >
        <div className="space-y-2">
          <Label htmlFor="email">{t("auth.field.email")}</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">{t("auth.field.password")}</Label>
            <Link
              to="/forgot-password"
              className="text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              {t("auth.login.forgot")}
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
          {t("auth.login.submit")}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {t("auth.login.noAccount")}{" "}
        <Link to="/signup" className="font-medium text-primary hover:underline">
          {t("auth.login.signupLink")}
        </Link>
      </p>
    </AuthShell>
  );
}
