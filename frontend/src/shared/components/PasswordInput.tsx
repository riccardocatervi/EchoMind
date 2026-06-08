import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/lib/utils";

type InputBaseProps = Omit<React.ComponentPropsWithoutRef<typeof Input>, "type">;

interface PasswordInputProps extends InputBaseProps {
  id: string;
  /**
   * Stato visibilita' controllato dall'esterno.
   * Se fornito, il componente opera in modalita' controllata e richiede anche
   * `onToggleShow`. Utile quando altri componenti (es. YetiAvatar) devono
   * reagire allo stato di visibilita'.
   * Se omesso, il componente gestisce il proprio stato interno.
   */
  show?: boolean;
  /** Richiesto quando `show` e' fornito (modalita' controllata). */
  onToggleShow?: () => void;
}

/**
 * Campo password con pulsante occhio (mostra / nascondi).
 *
 * Modalita' interna  (show assente): stato locale, autonomo.
 * Modalita' controllata (show presente): stato gestito dal parent.
 */
export function PasswordInput({
  id,
  show: externalShow,
  onToggleShow,
  className,
  ...props
}: PasswordInputProps) {
  const { t } = useTranslation();
  const [internalShow, setInternalShow] = useState(false);

  const isControlled = externalShow !== undefined;
  const visible = isControlled ? (externalShow ?? false) : internalShow;
  const toggle = isControlled
    ? (onToggleShow ?? (() => undefined))
    : () => setInternalShow((s) => !s);

  return (
    <div className="relative">
      <Input
        id={id}
        type={visible ? "text" : "password"}
        className={cn("pr-10", className)}
        {...props}
      />
      <button
        type="button"
        /*
         * onMouseDown con preventDefault: impedisce al browser di spostare il
         * focus dall'input password al pulsante quando l'utente clicca l'occhio.
         * Senza questa riga il campo perde il focus prima che onClick aggiorni
         * lo stato, causando l'abbassamento prematuro delle braccia dello yeti.
         * onClick rimane come gestore semantico del toggle.
         */
        onMouseDown={(e) => e.preventDefault()}
        onClick={toggle}
        tabIndex={-1}
        aria-label={visible ? t("auth.password.hide") : t("auth.password.show")}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {visible ? (
          <EyeOff className="size-4" aria-hidden="true" />
        ) : (
          <Eye className="size-4" aria-hidden="true" />
        )}
      </button>
    </div>
  );
}
