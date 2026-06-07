import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { AuthShell } from "@/features/auth/components/AuthShell";
import { supabase } from "@/features/auth/lib/supabaseClient";

/**
 * Pagina "Password dimenticata": invia un'email di reset tramite Supabase.
 *
 * Flusso:
 *   1. Utente inserisce la propria email e invia il form.
 *   2. `supabase.auth.resetPasswordForEmail` invia una magic-link all'email.
 *   3. L'utente clicca il link -> viene rimandato a /reset-password.
 *   4. ResetPasswordPage gestisce l'aggiornamento della password.
 *
 * NOTA: In Supabase Dashboard -> Authentication -> URL Configuration,
 * aggiungi "http://localhost:5173/reset-password" tra i Redirect URLs consentiti.
 * In produzione sostituisci con il dominio reale.
 */
export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    setError(null);
    setSubmitting(true);

    const { error: sbError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    setSubmitting(false);
    if (sbError) {
      setError(sbError.message);
      return;
    }
    setSuccess(true);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <AuthShell title={t("auth.forgot.title")} description={t("auth.forgot.description")}>
      {success ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-muted-foreground">{t("auth.forgot.success")}</p>
          <Link to="/login" className="block text-sm font-medium text-primary hover:underline">
            {t("auth.forgot.backToLogin")}
          </Link>
        </div>
      ) : (
        <>
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
                onChange={(e) => setEmail(e.target.value)}
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
              {t("auth.forgot.submit")}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            <Link to="/login" className="font-medium text-primary hover:underline">
              {t("auth.forgot.backToLogin")}
            </Link>
          </p>
        </>
      )}
    </AuthShell>
  );
}
