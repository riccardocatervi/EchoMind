import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { AuthShell } from "@/features/auth/components/AuthShell";
import { supabase } from "@/features/auth/lib/supabaseClient";

type PageState = "checking" | "ready" | "expired" | "success";

/**
 * Pagina di reset password: l'utente arriva qui dopo aver cliccato il link
 * ricevuto via email. Supabase JS SDK con `detectSessionInUrl: true` rileva
 * automaticamente i token nel hash/query e spara l'evento PASSWORD_RECOVERY
 * su `onAuthStateChange`.
 *
 * Flusso:
 *   checking -> Supabase rileva token e spara PASSWORD_RECOVERY -> ready
 *   ready    -> utente inserisce nuova password -> success
 *   expired  -> link non valido o gia' usato
 */
export function ResetPasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [pageState, setPageState] = useState<PageState>("checking");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    // Supabase fires PASSWORD_RECOVERY when it detects the reset token in the URL.
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setPageState("ready");
      }
    });

    // Se dopo 5 secondi non arriva l'evento, il link e' scaduto/invalido.
    const timeout = setTimeout(() => {
      setPageState((current) => (current === "checking" ? "expired" : current));
    }, 5_000);

    return () => {
      data.subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError(t("auth.reset.mismatch"));
      return;
    }
    if (password.length < 6) {
      setError(t("auth.reset.minLength"));
      return;
    }
    setSubmitting(true);
    const { error: sbError } = await supabase.auth.updateUser({ password });
    setSubmitting(false);
    if (sbError) {
      setError(sbError.message);
      return;
    }
    setPageState("success");
    // Dopo 2 secondi redirige al login
    setTimeout(() => void navigate("/login"), 2_000);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <AuthShell title={t("auth.reset.title")} description={t("auth.reset.description")}>
      {pageState === "checking" && (
        <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("auth.reset.checking")}
        </div>
      )}

      {pageState === "expired" && (
        <div className="space-y-4 text-center">
          <p className="text-sm text-destructive">{t("auth.reset.expired")}</p>
          <Link
            to="/forgot-password"
            className="block text-sm font-medium text-primary hover:underline"
          >
            {t("auth.forgot.backToLogin")}
          </Link>
        </div>
      )}

      {pageState === "success" && (
        <div className="space-y-4 text-center">
          <p className="text-sm text-muted-foreground">{t("auth.reset.success")}</p>
          <Link to="/login" className="block text-sm font-medium text-primary hover:underline">
            {t("auth.forgot.backToLogin")}
          </Link>
        </div>
      )}

      {pageState === "ready" && (
        <form
          ref={formRef}
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="password">{t("auth.reset.newPassword")}</Label>
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
          <div className="space-y-2">
            <Label htmlFor="confirm">{t("auth.reset.confirmPassword")}</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
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
            {t("auth.reset.submit")}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
