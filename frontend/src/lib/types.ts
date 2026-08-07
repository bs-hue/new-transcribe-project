/** Mirrors backend/app/schemas.py. Hand-written and small — one file to update
 *  when the contract changes, and no code-generation step in the build. */

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "member";
  is_active: boolean;
  /** null means the account signed up and is still waiting to be let in. */
  approved_at: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Platform {
  name: string;
  display_name: string;
}

export interface ExportFormat {
  format: string;
  display_name: string;
  extension: string;
  content_type: string;
  requires_segments: boolean;
  /** Whether several transcripts can be rendered into one file of this format. */
  combinable: boolean;
}

/** Who may create an account. Mirrors REGISTRATION_MODE on the server. */
export type RegistrationMode = "closed" | "approval" | "open";

export interface Meta {
  app_name: string;
  version: string;
  platforms: Platform[];
  export_formats: ExportFormat[];
  limits: {
    max_video_duration_seconds: number;
    max_video_filesize_bytes: number;
    max_urls_per_request: number;
  };
  transcription_provider: string;
  transcription_ready: boolean;
  transcription_error: string | null;
  registration_mode: RegistrationMode;
}

export interface Preview {
  url: string;
  valid: boolean;
  platform: string | null;
  platform_display_name: string | null;
  canonical_url: string | null;
  title: string | null;
  author: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  estimated_size_bytes: number | null;
  within_limits: boolean;
  limit_reasons: string[];
  warnings: string[];
  already_transcribed: boolean;
  error_code: string | null;
  error_message: string | null;
}

export interface SubmissionOutcome {
  url: string;
  accepted: boolean;
  job_id: string | null;
  video_id: string | null;
  platform: string | null;
  canonical_url: string | null;
  duplicate_of_existing_video: boolean;
  error_code: string | null;
  error_message: string | null;
}

export interface Submission {
  batch_id: string;
  accepted_count: number;
  rejected_count: number;
  results: SubmissionOutcome[];
}

export interface VideoSummary {
  id: string;
  platform: string;
  title: string | null;
  author: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  canonical_url: string;
  source_url: string;
  published_at: string | null;
  created_at: string;
}

export interface Segment {
  index: number;
  start: number;
  end: number;
  text: string;
  speaker: string | null;
}

export interface TranscriptSummary {
  id: string;
  video_id: string;
  language: string | null;
  provider: string;
  model: string | null;
  word_count: number;
  duration_seconds: number | null;
  created_at: string;
}

export interface TranscriptDetail extends TranscriptSummary {
  text: string;
  segments: Segment[];
  video?: VideoSummary | null;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  submitted_by?: string | null;
  submitted_by_name?: string | null;
  id: string;
  video_id: string;
  batch_id: string | null;
  status: JobStatus;
  stage: string;
  progress: number;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  video?: VideoSummary | null;
  transcript_id?: string | null;
}

export interface BatchStatus {
  batch_id: string;
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  jobs: Job[];
}

export interface VideoDetail extends VideoSummary {
  description: string | null;
  author_url: string | null;
  estimated_size_bytes: number | null;
  view_count: number | null;
  like_count: number | null;
  transcript: TranscriptDetail | null;
  transcript_count: number;
  latest_job: Job | null;
}

export interface Paged<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface SearchHit {
  transcript_id: string;
  video_id: string;
  snippet: string;
  rank: number;
  title: string | null;
  author: string | null;
  platform: string | null;
  thumbnail_url: string | null;
  canonical_url: string | null;
  duration_seconds: number | null;
  word_count: number;
  created_at: string | null;
}

export interface SearchResponse extends Paged<SearchHit> {
  query: string;
}

// --- dashboard ---------------------------------------------------------------

export interface RecentTranscript extends TranscriptSummary {
  video: VideoSummary | null;
}

export interface Dashboard {
  in_progress: number;
  finished_today: number;
  needs_attention: number;
  total_research: number;
  active_jobs: Job[];
  recent_transcripts: RecentTranscript[];
}

// --- settings ----------------------------------------------------------------

export interface SettingDefinition {
  key: string;
  label: string;
  help: string;
  kind: "int" | "str";
  minimum: number | null;
  maximum: number | null;
  choices: string[] | null;
  choice_labels: Record<string, string> | null;
  applies_to: string;
  unit: "seconds" | "bytes" | "count" | null;
}

export interface SettingsPayload {
  values: Record<string, string | number | null>;
  definitions: SettingDefinition[];
  transcription_provider: string;
  cookies_configured: boolean;
  worker_concurrency: number;
  environment: string;
}

export interface SystemCheckResult {
  name: string;
  ok: boolean;
  warning_only: boolean;
  detail: string;
  fix: string | null;
}

export interface SystemCheck {
  ok: boolean;
  results: SystemCheckResult[];
  text: string;
}
