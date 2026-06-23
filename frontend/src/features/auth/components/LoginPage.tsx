/**
 * Pagina di login con form email + password.
 *
 * Flusso di autenticazione:
 *   1. `credentialsSchema.safeParse(...)`: validazione Zod client-side (email formato,
 *      password minima). Mostra errore immediato PRIMA di chiamare Supabase → UX
 *      più reattiva (zero latenza per errori di formato).
 *   2. `signInWithPassword(email, password)`: chiama Supabase Auth.
 *   3. Se successo → `navigate("/documents", { replace: true })`.
 *      `replace` evita che il tasto "indietro" riporti al login dopo l'accesso.
 *
 * `Navigate replace` se già autenticato:
 *   Redirect diretto se `status === "authenticated"` (utente che riapre /login
 *   senza fare logout). Senza questo, l'utente autenticato vedrebbe il form vuoto.
 *
 * `formRef.current?.requestSubmit()` in `onKeyDown`:
 *   Invece di chiamare `handleSubmit` direttamente, `requestSubmit()` fa triggerare
 *   l'evento `submit` del form → attiva la validazione nativa del browser (es.
 *   `required`) prima di arrivare a `handleSubmit`. Più corretto di `submit()`.
 *
 * `YetiAvatar`:
 *   Mascotte animata che copre gli occhi quando la password è visibile
 *   (passwordFocused + passwordVisible). Stato di focus e valore email
 *   vengono passati all'avatar per animazioni sincronizzate.
 *
 * `noValidate` sul form:
 *   Disabilita la validazione nativa del browser (popup del browser su campo
 *   invalido). Gestiamo la validazione con Zod e mostriamo errori nel DOM.
 */
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { PasswordInput } from "@/shared/components/PasswordInput";
import { AuthShell } from "@/features/auth/components/AuthShell";
import { YetiAvatar } from "@/features/auth/components/YetiAvatar";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { credentialsSchema } from "@/features/auth/schemas/authSchema";

export function LoginPage() {
  const { t } = useTranslation();
  const { status, signInWithPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);

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
    <AuthShell
      title={t("auth.login.title")}
      description={t("auth.login.description")}
      icon={
        <YetiAvatar
          passwordFocused={passwordFocused}
          passwordVisible={showPassword}
          emailFocused={emailFocused}
          emailValue={email}
          emailInputRef={emailRef}
          className="h-32 w-32"
        />
      }
    >
      <form
        ref={formRef}
        onSubmit={(event) => void handleSubmit(event)}
        className="space-y-4"
        noValidate
      >
        <div className="space-y-2">
          <Label htmlFor="email">{t("auth.field.email")}</Label>
          <Input
            ref={emailRef}
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            onFocus={() => setEmailFocused(true)}
            onBlur={() => setEmailFocused(false)}
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
          <PasswordInput
            id="password"
            autoComplete="current-password"
            required
            value={password}
            show={showPassword}
            onToggleShow={() => setShowPassword((v) => !v)}
            onFocus={() => setPasswordFocused(true)}
            onBlur={() => setPasswordFocused(false)}
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
