// Контракт JSON бэкенда (src/flow/api.py). Меняете там, меняйте здесь.

export type PersonStatus = "ok" | "private" | "not_found" | "error";

export interface Person {
  username: string;
  display_name: string;
  plays: number;
  last_synced_at: number | null; // секунды UNIX
  status: PersonStatus;
  error: string | null;
}

export interface NewPerson {
  username: string;
  display_name: string;
}

export interface SyncResult {
  username: string;
  added: number;
  status: PersonStatus;
  error?: string;
}

export interface SyncResponse {
  results: SyncResult[];
}

export interface TopArtist {
  artist: string;
  plays: number;
}

export interface UserStats {
  name: string;
  plays: number;
  artists: number;
  heard_once: number;
  first_ts: number | null;
  last_ts: number | null;
  top_artists: TopArtist[];
  hours: number[]; // 24 числа
}

export interface Summary {
  people: number;
  plays: number;
  artists: number;
  density_percent: number;
  first_ts: number | null;
  last_ts: number | null;
}

export interface Similarity {
  users: string[];
  matrix: number[][]; // 0..1, matrix[i][j]
}

export interface ArtistMatrix {
  users: string[];
  artists: string[];
  plays: number[][]; // plays[человек][артист]
}

export interface Report {
  generated_at: number;
  summary: Summary;
  users: UserStats[];
  similarity: Similarity;
  matrix: ArtistMatrix;
}

export interface AuthResponse {
  token: string;
}

export interface SignupIn {
  username: string;
  consent: boolean;
  contact: string;
  website: string; // honeypot, всегда пустой у человека
  invite_code?: string; // из ссылки /guestform?invite=...; сервер пока его не проверяет
}

export interface SignupRequest {
  id: number;
  username: string;
  contact: string | null;
  consent_at: number;
  created_at: number;
  status: "pending" | "approved" | "rejected";
}

export interface DecisionResponse {
  id: number;
  status: "approved" | "rejected";
}
