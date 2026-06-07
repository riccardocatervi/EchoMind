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
