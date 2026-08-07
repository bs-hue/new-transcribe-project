/** Typed API client.
 *
 *  One place that knows the base URL, the bearer token, and how the backend
 *  reports errors — so components just `await api.something()` and catch one
 *  error type.
 */

import type {
  BatchStatus,
  Job,
  Meta,
  Paged,
  Preview,
  RegistrationMode,
  SearchResponse,
  Dashboard,
  SettingsPayload,
  Submission,
  SystemCheck,
  TokenResponse,
  TranscriptDetail,
  User,
  VideoDetail,
  VideoSummary,
} from "./types";

/** Where the API lives.
 *
 *  Empty means "the same origin as this page", which is how the app is served
 *  in Docker and in production: nginx passes /api through to the backend, so
 *  the browser never needs to know a second address. A value is only needed
 *  when the two are genuinely apart — running `npm run dev` against a backend
 *  on another port, for instance. */
const BASE_URL = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ""
).replace(/\/$/, "");

const TOKEN_KEY = "research-hub.token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string = "error",
    readonly status: number = 0,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// --- token storage -----------------------------------------------------------

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Fires when a request comes back 401, so the app can bounce to the login
 *  screen from anywhere without every caller handling it. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler = () => {};
export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  onUnauthorized = handler;
}

// --- plumbing ----------------------------------------------------------------

function authHeaders(includeJson: boolean): Record<string, string> {
  const headers: Record<string, string> = {};
  if (includeJson) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function toError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    if (typeof body?.message === "string") {
      return new ApiError(body.message, body.code ?? "error", response.status);
    }
    if (body?.detail) {
      const detail = Array.isArray(body.detail)
        ? body.detail.map((d: { msg?: string }) => d.msg ?? "Invalid input").join("; ")
        : String(body.detail);
      return new ApiError(detail, "validation_error", response.status);
    }
  } catch {
    /* fall through */
  }
  return new ApiError(`Request failed with status ${response.status}.`, "error", response.status);
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { ...authHeaders(init?.body !== undefined), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      "Cannot reach the server. Check that the backend is running.",
      "network_error",
    );
  }

  if (response.status === 401) {
    tokenStore.clear();
    onUnauthorized();
  }
  if (!response.ok) throw await toError(response);
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

/** Downloads are authenticated, so they cannot be a plain <a href>. Fetch the
 *  bytes with the token attached, then hand the blob to the browser. */
async function download(path: string, init?: RequestInit): Promise<void> {
  const response = await send(path, init);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const filename = match?.[1] ?? "download";

  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// --- endpoints ---------------------------------------------------------------

export const api = {
  // auth
  login: (email: string, password: string) =>
    request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>("/api/auth/me"),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<User>("/api/auth/me/password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  users: () => request<User[]>("/api/auth/users"),

  createUser: (body: {
    email: string;
    password: string;
    full_name?: string;
    role: "admin" | "member";
  }) => request<User>("/api/auth/users", { method: "POST", body: JSON.stringify(body) }),

  updateUser: (
    userId: string,
    body: { full_name?: string; role?: "admin" | "member"; is_active?: boolean },
  ) =>
    request<User>(`/api/auth/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteUser: (userId: string) =>
    request<void>(`/api/auth/users/${userId}`, { method: "DELETE" }),

  // discovery
  meta: () => request<Meta>("/api/meta"),

  // dashboard
  dashboard: () => request<Dashboard>("/api/dashboard"),

  // settings
  settings: () => request<SettingsPayload>("/api/settings"),

  updateSettings: (values: Record<string, string | number | null>) =>
    request<SettingsPayload>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({ values }),
    }),

  systemCheck: (deep = false) =>
    request<SystemCheck>(`/api/settings/system-check${deep ? "?deep=true" : ""}`),

  // submission
  preview: (urls: string[]) =>
    request<{ results: Preview[] }>("/api/videos/preview", {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),

  submit: (urls: string[], language?: string) =>
    request<Submission>("/api/videos", {
      method: "POST",
      body: JSON.stringify({ urls, language: language || null }),
    }),

  // jobs
  batchStatus: (batchId: string) => request<BatchStatus>(`/api/jobs/batch/${batchId}`),
  job: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  jobs: (params: { status?: string; batch_id?: string; limit?: number; offset?: number }) =>
    request<Paged<Job>>(`/api/jobs${query(params)}`),
  retryJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" }),
  cancelJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),

  // library
  videos: (params: {
    platform?: string;
    author?: string;
    has_transcript?: boolean;
    limit?: number;
    offset?: number;
  }) => request<Paged<VideoSummary>>(`/api/videos${query(params)}`),

  video: (videoId: string) => request<VideoDetail>(`/api/videos/${videoId}`),

  deleteVideo: (videoId: string) =>
    request<void>(`/api/videos/${videoId}`, { method: "DELETE" }),

  transcript: (transcriptId: string) =>
    request<TranscriptDetail>(`/api/transcripts/${transcriptId}`),

  // search
  search: (params: {
    q: string;
    platform?: string;
    author?: string;
    limit?: number;
    offset?: number;
  }) => request<SearchResponse>(`/api/search${query(params)}`),

  // export
  registrationMode: () =>
    request<{ mode: RegistrationMode }>("/api/auth/registration"),

  register: (body: { email: string; password: string; full_name?: string }) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  approveUser: (userId: string) =>
    request<User>(`/api/auth/users/${userId}/approve`, { method: "POST" }),

  exportTranscript: (transcriptId: string, format: string) =>
    download(`/api/transcripts/${transcriptId}/export?format=${encodeURIComponent(format)}`),

  bulkExport: (body: {
    format: string;
    transcript_ids?: string[];
    video_ids?: string[];
    query?: string;
    /** One file holding every transcript. False asks for a ZIP instead. */
    combine?: boolean;
  }) => download("/api/exports", { method: "POST", body: JSON.stringify(body) }),
};
