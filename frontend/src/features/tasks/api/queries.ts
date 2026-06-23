/**
 * Hook per monitorare lo stato di un singolo task Celery.
 *
 * Polling con `refetchInterval` condizionale:
 *   Con `poll: true`, l'hook ri-fetcha ogni 2s finché il task non è terminale.
 *   Quando il task raggiunge "succeeded" o "failed", il polling si ferma da solo
 *   (ritorna `false` dal callback `refetchInterval`).
 *
 * Perché 2s e non 3s (come useDocument):
 *   I task Celery sono operazioni brevi (es. trigger di ri-estrazione).
 *   L'utente aspetta il feedback di completamento con meno pazienza rispetto
 *   all'elaborazione lunga del documento. 2s è un buon compromesso per
 *   un feedback reattivo senza sovraccaricare il backend.
 *
 * `poll: boolean` opzionale (default false):
 *   Quando non si passa `poll`, l'hook legge la cache esistente senza avviare
 *   polling (utile per leggere il result di un task già terminato).
 */
import { useQuery } from "@tanstack/react-query";

import { taskKeys } from "@/features/tasks/api/keys";
import { getTask } from "@/features/tasks/api/requests";

/**
 * Stato di un task. Con `poll: true` rinfresca ogni 2s finché non raggiunge
 * uno stato terminale (succeeded/failed), poi si ferma automaticamente.
 */
export function useTask(taskId: string | undefined, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: taskKeys.detail(taskId ?? ""),
    queryFn: () => getTask(taskId as string),
    // Non avvia la query se taskId non è disponibile (evita 404).
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      if (!options.poll) return false;
      const status = query.state.data?.status;
      // Ferma il polling quando il task è terminale.
      if (status === "succeeded" || status === "failed") return false;
      return 2000; // poll ogni 2s durante elaborazione attiva
    },
  });
}
