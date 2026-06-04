import { apiFetch } from "@/lib/apiClient";
import type { ProfileRead, ProfileUpdate } from "@/types/api";

/** Ritorna il profile dell'utente corrente (creato lazy se non esiste). */
export function getMyProfile(): Promise<ProfileRead> {
  return apiFetch<ProfileRead>("/profiles/me");
}

export function updateMyProfile(payload: ProfileUpdate): Promise<ProfileRead> {
  return apiFetch<ProfileRead>("/profiles/me", { method: "PATCH", body: payload });
}
