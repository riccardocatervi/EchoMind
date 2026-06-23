/**
 * Query Key Factory per i task Celery.
 *
 * I task hanno solo due chiavi: `all` (lista) e `detail` (singolo).
 * `detail` = ["tasks", taskId]: permette a `invalidateQueries` di
 * aggiornare il singolo task senza toccare la lista (e viceversa).
 */
export const taskKeys = {
  all: ["tasks"] as const,
  detail: (id: string) => [...taskKeys.all, id] as const,
};
