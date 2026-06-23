/**
 * Dialog modale per l'upload di un documento.
 *
 * Flusso in 3 fasi (gestito da `useUploadDocument` in mutations.ts):
 *   1. Selezione file:    FileDropzone → `setFile(file)`
 *   2. Upload su B2:     XHR diretto con `onProgress` → aggiorna `progress` (0→100)
 *   3. Conferma backend: POST /confirm → validazione MIME + status=uploaded
 *
 * Perché il dialog non si chiude durante l'upload (`upload.isPending`):
 *   Chiudere il dialog durante un upload XHR abortirebbe la trasmissione.
 *   `handleOpenChange` controlla questo: se `isPending`, il click fuori dal dialog
 *   o il tasto Escape non ha effetto. L'utente è costretto ad aspettare o a
 *   cliccare "Annulla" esplicitamente (che però non cancella l'XHR in volo — limite
 *   accettato: il presigned URL scade e il backend non vede l'oggetto B2).
 *
 * Perché `progress < 100 ? t("upload.progress") : t("upload.checking")`:
 *   Quando XHR raggiunge 100%, la fase 3 (confirmUpload) sta ancora girando sul
 *   backend (HEAD + magic bytes). Mostrare "Verifica in corso..." durante questo
 *   intervallo evita di sembrare bloccato al 100%.
 *
 * `reset()` ripristina lo stato locale alla chiusura del dialog: senza questo,
 *   riaprendo il dialog il file precedente sarebbe ancora selezionato.
 */
import { useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import { Progress } from "@/shared/components/ui/progress";
import { useUploadDocument } from "@/features/documents/api/mutations";
import { FileDropzone } from "@/features/documents/components/FileDropzone";

export function UploadDialog() {
  const { t } = useTranslation();
  const upload = useUploadDocument();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);

  function reset() {
    setFile(null);
    setProgress(0);
  }

  function handleOpenChange(next: boolean) {
    if (upload.isPending) return; // non chiudere mentre carica
    setOpen(next);
    if (!next) reset();
  }

  function startUpload() {
    if (!file) return;
    setProgress(0);
    upload.mutate(
      { file, onProgress: setProgress },
      {
        onSuccess: (doc) => {
          if (doc.status === "failed") {
            toast.error(t("upload.error.mimeType"));
          } else {
            toast.success(t("upload.success"));
          }
          setOpen(false);
          reset();
        },
        onError: (error) => {
          toast.error(error.message || t("upload.error.failed"));
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Upload aria-hidden="true" />
          {t("docs.upload")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("upload.dialog.title")}</DialogTitle>
          <DialogDescription>{t("upload.dialog.description")}</DialogDescription>
        </DialogHeader>

        <FileDropzone file={file} onSelect={setFile} disabled={upload.isPending} />

        {upload.isPending && (
          <div className="space-y-1">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">
              {progress < 100 ? t("upload.progress", { percent: progress }) : t("upload.checking")}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={upload.isPending}
          >
            {t("upload.cancel")}
          </Button>
          <Button onClick={startUpload} disabled={!file || upload.isPending}>
            {upload.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
            {t("upload.submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
