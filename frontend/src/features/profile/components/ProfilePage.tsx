import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { PasswordInput } from "@/shared/components/PasswordInput";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { api } from "@/shared/api/axios";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { supabase } from "@/features/auth/lib/supabaseClient";
import { profileKeys } from "@/features/profile/api/keys";
import { updateMyProfile } from "@/features/profile/api/requests";
import { useProfile } from "@/features/profile/api/queries";
import type { ProfileRead } from "@/features/profile/schemas/profile";
import { SUPPORTED_LANGUAGES, type SupportedLang } from "@/shared/i18n";

/**
 * Pagina profilo: saluto personalizzato + cambio nome, email e password.
 *
 * - Cambio nome: aggiorna user_metadata.first_name / last_name via updateUser.
 * - Cambio email: Supabase invia una confirmation email al NUOVO indirizzo.
 * - Cambio password: aggiornamento immediato (nessuna conferma richiesta).
 */
export function ProfilePage() {
  const { t } = useTranslation();
  const { user } = useAuth();

  // Legge il nome da user_metadata (salvato al signup).
  // Fallback: mostra l'email se l'utente non ha ancora un nome.
  const firstName = (user?.user_metadata?.first_name as string | undefined) ?? "";
  const displayName = firstName || (user?.email ?? "");

  return (
    <div className="space-y-6">
      {/* Back link -- sticky: rimane visibile mentre si scrolla la pagina. */}
      <div className="sticky top-14 z-10 -mx-1 rounded-md bg-background/90 px-1 py-1.5 backdrop-blur-sm">
        <Link
          to="/documents"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("profile.back")}
        </Link>
      </div>

      {/* Saluto personalizzato -- l'email corrente e' visibile nell'apposita card. */}
      <div>
        <h1 className="font-mono text-2xl font-semibold tracking-tight">
          {t("profile.greeting", { name: displayName })}
        </h1>
      </div>

      {/* Tutte le card in un'unica griglia -- su xl a 3 colonne:            */}
      {/* riga 1: Nome | Email | Password                                    */}
      {/* riga 2: Lingua di output | Elimina account (affiancati e simmetrici) */}
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <NameSection
          initialFirstName={firstName}
          initialLastName={(user?.user_metadata?.last_name as string | undefined) ?? ""}
        />
        <EmailSection />
        <PasswordSection />
        <LanguageSection />
        <DeleteAccountSection />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Sezione modifica nome                                                       */
/* -------------------------------------------------------------------------- */
function NameSection({
  initialFirstName,
  initialLastName,
}: {
  initialFirstName: string;
  initialLastName: string;
}) {
  const { t } = useTranslation();
  const [firstName, setFirstName] = useState(initialFirstName);
  const [lastName, setLastName] = useState(initialLastName);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    const { error } = await supabase.auth.updateUser({
      data: { first_name: firstName.trim(), last_name: lastName.trim() },
    });
    setSubmitting(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success(t("profile.name.success"));
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="text-base">{t("profile.name.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          ref={formRef}
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="profile-first-name">{t("profile.name.firstName")}</Label>
            <Input
              id="profile-first-name"
              type="text"
              autoComplete="given-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="profile-last-name">{t("profile.name.lastName")}</Label>
            <Input
              id="profile-last-name"
              type="text"
              autoComplete="family-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={submitting || (!firstName.trim() && !lastName.trim())}
          >
            {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
            {t("profile.name.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Sezione cambio email                                                        */
/* -------------------------------------------------------------------------- */
function EmailSection() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [newEmail, setNewEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newEmail.trim()) return;
    setSubmitting(true);
    const { error } = await supabase.auth.updateUser({ email: newEmail.trim() });
    setSubmitting(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success(t("profile.email.success"));
    setNewEmail("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="text-base">{t("profile.email.title")}</CardTitle>
        {user?.email && (
          <CardDescription className="text-sm">
            {t("profile.email.current")}:{" "}
            <span className="font-medium text-foreground">{user.email}</span>
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <form
          ref={formRef}
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="new-email">{t("profile.email.new")}</Label>
            <Input
              id="new-email"
              type="email"
              autoComplete="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
          <Button type="submit" size="sm" disabled={submitting || !newEmail.trim()}>
            {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
            {t("profile.email.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Sezione cambio password                                                     */
/* -------------------------------------------------------------------------- */
function PasswordSection() {
  const { t } = useTranslation();
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError(t("profile.password.mismatch"));
      return;
    }
    setSubmitting(true);
    const { error: sbError } = await supabase.auth.updateUser({ password: newPassword });
    setSubmitting(false);
    if (sbError) {
      toast.error(sbError.message);
      return;
    }
    toast.success(t("profile.password.success"));
    setNewPassword("");
    setConfirm("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="text-base">{t("profile.password.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          ref={formRef}
          onSubmit={(event) => void handleSubmit(event)}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="new-password">{t("profile.password.new")}</Label>
            <PasswordInput
              id="new-password"
              autoComplete="new-password"
              minLength={6}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">{t("profile.password.confirm")}</Label>
            <PasswordInput
              id="confirm-password"
              autoComplete="new-password"
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
          <Button type="submit" size="sm" disabled={submitting || !newPassword}>
            {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
            {t("profile.password.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Sezione lingua di output                                                    */
/* -------------------------------------------------------------------------- */
function LanguageSection() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: profile } = useProfile();
  const [submitting, setSubmitting] = useState(false);

  // Fonte di verita': solo il profilo (lingua di OUTPUT, indipendente dalla UI).
  // Default 'it' se il profilo non e' ancora caricato.
  const current = (profile?.preferred_language ?? "it") as SupportedLang;

  async function handleSelect(lang: SupportedLang) {
    if (lang === current || submitting) return;
    setSubmitting(true);
    try {
      const updated = await updateMyProfile({ preferred_language: lang });
      // Aggiorna solo la cache del profilo: la lingua di output NON cambia la UI.
      queryClient.setQueryData<ProfileRead>(profileKeys.me, updated);
      toast.success(t("profile.language.success"));
    } catch {
      toast.error(t("profile.language.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="shadow-[0_0_30px_rgba(99,120,220,0.15)] ring-1 ring-white/5">
      <CardHeader>
        <CardTitle className="text-base">{t("profile.language.title")}</CardTitle>
        <CardDescription className="text-sm">{t("profile.language.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <Button
              key={lang}
              variant={lang === current ? "default" : "outline"}
              size="sm"
              disabled={submitting}
              onClick={() => void handleSelect(lang)}
            >
              {submitting && lang !== current && (
                <Loader2 className="animate-spin" aria-hidden="true" />
              )}
              {t(`profile.language.${lang}`)}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Sezione eliminazione account (zona pericolo)                               */
/* -------------------------------------------------------------------------- */

/**
 * Card con glow rosso che avverte l'utente prima di eliminare l'account.
 *
 * Flusso:
 *  1. Pulsante "Elimina account" apre un AlertDialog con descrizione esplicita.
 *  2. L'utente conferma → chiamata DELETE /users/me.
 *  3. In caso di successo: signOut() → ProtectedRoute redirige a "/".
 *  4. In caso di errore: toast di errore, nessuna navigazione.
 *
 * Perche' non basta signOut(): il JWT e' ancora valido fino alla scadenza.
 * Chiamare signOut() pulisce il token locale; il backend ha gia' eliminato
 * l'utente da auth.users, quindi il JWT non puo' piu' autenticare nulla.
 */
function DeleteAccountSection() {
  const { t } = useTranslation();
  const { signOut } = useAuth();
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.delete("/users/me");
      toast.success(t("profile.delete.success"));
      // Pulisce la sessione locale: ProtectedRoute redirige a "/" automaticamente.
      void signOut();
    } catch {
      toast.error(t("profile.delete.error"));
      setDeleting(false);
    }
  }

  return (
    <section aria-labelledby="delete-account-heading">
      {/*
       * Glow rosso: segnala la zona pericolo senza essere eccessivamente aggressivo.
       * `ring-red-500/20` + `shadow-[...rgba(239,68,68,...)]` = alone rosso tenue.
       */}
      <Card className="border-red-500/30 shadow-[0_0_30px_rgba(239,68,68,0.18)] ring-1 ring-red-500/20">
        <CardHeader>
          <CardTitle className="text-base text-destructive" id="delete-account-heading">
            {t("profile.delete.title")}
          </CardTitle>
          <CardDescription className="text-sm">{t("profile.delete.warning")}</CardDescription>
        </CardHeader>
        <CardContent>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm" disabled={deleting}>
                {deleting && <Loader2 className="animate-spin" aria-hidden="true" />}
                {t("profile.delete.trigger")}
              </Button>
            </AlertDialogTrigger>

            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("profile.delete.dialog.title")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t("profile.delete.dialog.description")}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("profile.delete.dialog.cancel")}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => void handleDelete()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {t("profile.delete.dialog.confirm")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </section>
  );
}
