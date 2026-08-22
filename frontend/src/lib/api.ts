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

// --- in-memory cache ---------------------------------------------------------

const apiCache = new Map<string, unknown>();

export function clearApiCache(pathPrefix?: string) {
  if (!pathPrefix) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (key.startsWith(pathPrefix)) {
      apiCache.delete(key);
    }
  }
}

async function cachedRequest<T>(path: string, force = false, init?: RequestInit): Promise<T> {
  if (!force && apiCache.has(path)) {
    return apiCache.get(path) as T;
  }
  const result = await request<T>(path, init);
  apiCache.set(path, result);
  return result;
}

// --- endpoints ---------------------------------------------------------------

export const api = {
  clearCache: clearApiCache,

  // auth
  login: (email: string, password: string) => {
    clearApiCache();
    return request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  me: () => request<User>("/api/auth/me"),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<User>("/api/auth/me/password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  users: (force = false) => cachedRequest<User[]>("/api/auth/users", force),

  createUser: (body: {
    email: string;
    password: string;
    full_name?: string;
    role: "admin" | "member";
  }) => {
    clearApiCache("/api/auth/users");
    return request<User>("/api/auth/users", { method: "POST", body: JSON.stringify(body) });
  },

  updateUser: (
    userId: string,
    body: { full_name?: string; role?: "admin" | "member"; is_active?: boolean },
  ) => {
    clearApiCache("/api/auth/users");
    return request<User>(`/api/auth/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteUser: (userId: string) => {
    clearApiCache("/api/auth/users");
    return request<void>(`/api/auth/users/${userId}`, { method: "DELETE" });
  },

  // discovery
  meta: (force = false) => cachedRequest<Meta>("/api/meta", force),

  // dashboard
  dashboard: (force = false) => cachedRequest<Dashboard>("/api/dashboard", force),

  // settings
  settings: (force = false) => cachedRequest<SettingsPayload>("/api/settings", force),

  updateSettings: (values: Record<string, string | number | null>) => {
    clearApiCache("/api/settings");
    return request<SettingsPayload>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({ values }),
    });
  },

  systemCheck: (deep = false) =>
    request<SystemCheck>(`/api/settings/system-check${deep ? "?deep=true" : ""}`),

  // submission
  preview: (urls: string[]) =>
    request<{ results: Preview[] }>("/api/videos/preview", {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),

  submit: (urls: string[], language?: string) => {
    clearApiCache("/api/dashboard");
    clearApiCache("/api/jobs");
    clearApiCache("/api/videos");
    return request<Submission>("/api/videos", {
      method: "POST",
      body: JSON.stringify({ urls, language: language || null }),
    });
  },

  // jobs
  batchStatus: (batchId: string) => request<BatchStatus>(`/api/jobs/batch/${batchId}`),
  job: (jobId: string, force = false) => cachedRequest<Job>(`/api/jobs/${jobId}`, force),
  jobs: (params: { status?: string; batch_id?: string; limit?: number; offset?: number }, force = false) =>
    cachedRequest<Paged<Job>>(`/api/jobs${query(params)}`, force),
  retryJob: (jobId: string) => {
    clearApiCache("/api/dashboard");
    clearApiCache("/api/jobs");
    return request<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" });
  },
  cancelJob: (jobId: string) => {
    clearApiCache("/api/dashboard");
    clearApiCache("/api/jobs");
    return request<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  },

  // library
  videos: (
    params: {
      platform?: string;
      author?: string;
      has_transcript?: boolean;
      limit?: number;
      offset?: number;
    },
    force = false,
  ) => cachedRequest<Paged<VideoSummary>>(`/api/videos${query(params)}`, force),

  video: (videoId: string, force = false) =>
    cachedRequest<VideoDetail>(`/api/videos/${videoId}`, force),

  deleteVideo: (videoId: string) => {
    clearApiCache("/api/dashboard");
    clearApiCache("/api/videos");
    return request<void>(`/api/videos/${videoId}`, { method: "DELETE" });
  },

  transcript: (transcriptId: string, force = false) =>
    cachedRequest<TranscriptDetail>(`/api/transcripts/${transcriptId}`, force),

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
