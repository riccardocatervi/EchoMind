import { useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { FileDropzone } from "@/features/documents/FileDropzone";
import { useUploadDocument } from "@/hooks/upload";

export function UploadDialog() {
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
            toast.error("Il contenuto del file non corrisponde al tipo dichiarato");
          } else {
            toast.success("Documento caricato. Elaborazione avviata.");
          }
          setOpen(false);
          reset();
        },
        onError: (error) => {
          toast.error(error.message || "Upload fallito");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Upload aria-hidden="true" />
          Carica documento
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Carica un documento</DialogTitle>
          <DialogDescription>
            Testo (PDF, DOCX, TXT) o audio (MP3, WAV, M4A). Dopo il caricamento partono
            automaticamente trascrizione ed estrazione del grafo.
          </DialogDescription>
        </DialogHeader>

        <FileDropzone file={file} onSelect={setFile} disabled={upload.isPending} />

        {upload.isPending && (
          <div className="space-y-1">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">
              {progress < 100 ? `Caricamento... ${progress}%` : "Verifica del file in corso..."}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={upload.isPending}
          >
            Annulla
          </Button>
          <Button onClick={startUpload} disabled={!file || upload.isPending}>
            {upload.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
            Carica
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
