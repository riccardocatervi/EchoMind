/**
 * Carica un File direttamente su B2 col presigned URL (PUT), bypassando il
 * backend. Usa XMLHttpRequest (non fetch) perche' espone gli eventi di
 * progresso dell'upload.
 *
 * IMPORTANTE: il presigned URL del backend firma sia il Content-Type sia il
 * Content-Length. Quindi:
 *  - il `contentType` passato qui DEVE essere identico al mime_type dichiarato
 *    in initUpload (altrimenti B2 risponde 403 SignatureDoesNotMatch);
 *  - il body e' il File: il browser imposta Content-Length = file.size, che
 *    combacia con il size_bytes dichiarato.
 *
 * NB: il PUT e' cross-origin, quindi il bucket B2 deve avere una regola CORS che
 * consenta PUT (e l'header Content-Type) dall'origin del frontend.
 */
export function uploadToB2(
  uploadUrl: string,
  file: File,
  contentType: string,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", contentType);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload a B2 fallito (HTTP ${xhr.status})`));
      }
    };
    xhr.onerror = () =>
      reject(new Error("Errore di rete durante l'upload a B2 (verifica la CORS del bucket)"));
    xhr.onabort = () => reject(new Error("Upload annullato"));

    xhr.send(file);
  });
}
