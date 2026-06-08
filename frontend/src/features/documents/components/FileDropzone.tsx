import { useRef, useState, type DragEvent } from "react";
import { UploadCloud, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { formatBytes } from "@/shared/lib/format";
import { cn } from "@/shared/lib/utils";
import { ALLOWED_MIME_TYPES, MAX_UPLOAD_SIZE_BYTES } from "@/features/documents/schemas/document";

const ACCEPT = ALLOWED_MIME_TYPES.join(",");

interface FileDropzoneProps {
  file: File | null;
  onSelect: (file: File | null) => void;
  disabled?: boolean;
}

/** Area drag&drop + file picker con validazione MIME/size lato client. */
export function FileDropzone({ file, onSelect, disabled }: FileDropzoneProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const maxLabel = formatBytes(MAX_UPLOAD_SIZE_BYTES);

  function validateAndSelect(candidate: File) {
    if (!(ALLOWED_MIME_TYPES as readonly string[]).includes(candidate.type)) {
      toast.error(t("dropzone.unsupportedType"));
      return;
    }
    if (candidate.size > MAX_UPLOAD_SIZE_BYTES) {
      toast.error(t("dropzone.tooLarge", { max: maxLabel }));
      return;
    }
    onSelect(candidate);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const dropped = event.dataTransfer.files[0];
    if (dropped) validateAndSelect(dropped);
  }

  if (file) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-md border bg-muted/40 p-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{file.name}</p>
          <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={t("dropzone.removeFile")}
          disabled={disabled}
          onClick={() => onSelect(null)}
        >
          <X aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed p-8 text-center transition-colors",
        dragging ? "border-primary bg-primary/5" : "border-input hover:bg-accent/40",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <UploadCloud className="size-8 text-muted-foreground" aria-hidden="true" />
      <p className="text-sm font-medium">{t("dropzone.hint")}</p>
      <p className="text-xs text-muted-foreground">{t("dropzone.formats", { max: maxLabel })}</p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(event) => {
          const selected = event.target.files?.[0];
          if (selected) validateAndSelect(selected);
          event.target.value = "";
        }}
      />
    </div>
  );
}
