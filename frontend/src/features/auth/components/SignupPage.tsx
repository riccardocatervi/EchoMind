import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { AuthShell } from "@/features/auth/components/AuthShell";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { signupSchema } from "@/features/auth/schemas/authSchema";

/**
 * Form di registrazione: nome, cognome, email, password.
 * Nome e cognome vengono salvati in user_metadata di Supabase
 * (accessibili poi come user.user_metadata.first_name / last_name).
 */
export function SignupPage() {
  const { t } = useTranslation();
  const { status, signUp } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);

  if (status === "authenticated") return <Navigate to="/documents" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const parsed = signupSchema.safeParse({ firstName, lastName, email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    setSubmitting(true);
    const { data, error: authError } = await signUp(parsed.data.email, parsed.data.password, {
      first_name: parsed.data.firstName,
      last_name: parsed.data.lastName,
    });
    setSubmitting(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    if (data.session) {
      navigate("/documents", { replace: true });
      return;
    }
    // Email confirmation richiesta: mostra messaggio informativo
    setInfo(t("auth.signup.confirmEmail"));
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <AuthShell title={t("auth.signup.title")} description={t("auth.signup.description")}>
      <form
        ref={formRef}
        onSubmit={(event) => void handleSubmit(event)}
        className="space-y-4"
        noValidate
      >
        {/* Nome + Cognome affiancati */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="first-name">{t("auth.signup.firstName")}</Label>
            <Input
              id="first-name"
              type="text"
              autoComplete="given-name"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="last-name">{t("auth.signup.lastName")}</Label>
            <Input
              id="last-name"
              type="text"
              autoComplete="family-name"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">{t("auth.field.email")}</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">{t("auth.field.password")}</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={onKeyDown}
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
          {t("auth.signup.submit")}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {t("auth.signup.hasAccount")}{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          {t("auth.signup.loginLink")}
        </Link>
      </p>
    </AuthShell>
  );
}
