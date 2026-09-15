/**
 * Types mirroring the API contract.
 *
 * Field names deliberately match the wire format exactly (snake_case), rather
 * than being converted to camelCase. A conversion layer is one more place for a
 * typo to hide, and it makes comparing this file against
 * docs/API_SPECIFICATION.md harder than it needs to be.
 *
 * These types are hand-written for now; once the backend is further along they
 * can be generated from its OpenAPI schema, which removes drift entirely.
 */

export type HealthStatus = 'ok' | 'degraded';
export type CheckStatus = 'ok' | 'error' | 'disabled';

/** `GET /health` */
export interface HealthResponse {
  status: HealthStatus;
  version: string;
  checks: Record<string, CheckStatus>;
}

/** `GET /config/public` — the limits the UI renders against. */
export interface PublicConfig {
  summarize_available: boolean;
  max_urls_per_batch: number;
  max_video_duration_seconds: number;
  supported_formats: string[];
  default_model: string;
  available_models: string[];
  manual_retry_enabled: boolean;
  max_attempts: number;
  playlists_supported: boolean;
}
