/**
 * Mirror TypeScript degli schemi Pydantic del backend: SINGLE SOURCE OF TRUTH
 * lato client per il contratto API. Un cambio di contratto non riflesso qui
 * rompe la compilazione (`tsc`) -- rete di sicurezza end-to-end.
 *
 * Tenere allineato con:
 *   backend/src/echomind/schemas/*   (shape dei DTO)
 *   backend/src/echomind/db/models/* (valori degli enum)
 *
 * NB: in JSON i `datetime` arrivano come stringhe ISO-8601 e gli UUID come stringhe.
 */

export type UUID = string;
export type ISODateTime = string;

// --- Enum (mirror degli StrEnum backend) ---------------------------------
export type DocumentStatus = "pending" | "uploaded" | "failed";
export type TaskStatus = "queued" | "running" | "succeeded" | "failed";
export type TaskType = "echo" | "transcribe" | "extract";
export type SourceType = "document" | "audio";

// --- Envelope d'errore standard (main.py _make_response) ------------------
export interface ErrorResponse {
  detail: string;
  code: string | null;
}

// --- Profile --------------------------------------------------------------
export interface ProfileRead {
  id: UUID;
  display_name: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ProfileUpdate {
  display_name?: string | null;
}

// --- Document -------------------------------------------------------------
export interface DocumentRead {
  id: UUID;
  owner_id: UUID;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  failure_reason: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface DocumentInitUpload {
  filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface DocumentInitUploadResponse {
  document_id: UUID;
  upload_url: string;
  expires_at: ISODateTime;
}

// --- Task -----------------------------------------------------------------
export interface TaskRead {
  id: UUID;
  owner_id: UUID;
  task_type: string;
  status: TaskStatus;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  retries: number;
  started_at: ISODateTime | null;
  finished_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface TaskEnqueuedResponse {
  task_id: UUID;
  status: TaskStatus;
}

// --- Transcript (M4) ------------------------------------------------------
export interface TranscriptRead {
  id: UUID;
  document_id: UUID;
  owner_id: UUID;
  source_type: SourceType;
  content: string;
  language: string | null;
  char_count: number;
  meta: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

// --- Summary (M5) ---------------------------------------------------------
export interface SummarySection {
  title: string;
  content: string;
}

export interface SummaryRead {
  id: UUID;
  document_id: UUID;
  owner_id: UUID;
  overview: string;
  sections: SummarySection[];
  meta: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

// --- Graph (M5) -----------------------------------------------------------
export interface GraphNode {
  id: UUID;
  name: string;
  type: string;
  description: string | null;
  community: number | null;
}

export interface GraphEdge {
  source: UUID;
  target: UUID;
  type: string;
  description: string | null;
}

export interface GraphRead {
  document_id: UUID;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  relationship_count: number;
  community_count: number;
}

// --- MIME whitelist (mirror di schemas/document.ALLOWED_MIME_TYPES) -------
// Usata dal file picker per validare lato client prima dell'upload.
export const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // DOCX
  "text/plain",
  "audio/mpeg", // MP3
  "audio/wav",
  "audio/x-wav",
  "audio/mp4", // M4A
  "audio/x-m4a",
] as const;

export type AllowedMimeType = (typeof ALLOWED_MIME_TYPES)[number];
