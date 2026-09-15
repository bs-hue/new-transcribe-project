/**
 * API error handling.
 *
 * The backend returns every failure in one shape (API_SPECIFICATION §1.1). This
 * module parses that shape and turns error *codes* into sentences a person can
 * act on. Doing it here, once, means no component ever renders a raw error
 * string — and a wording change happens in exactly one place.
 */

export interface ApiErrorDetail {
  field: string;
  issue: string;
}

/** The backend's error envelope. */
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail[];
    correlation_id?: string | null;
  };
}

/**
 * Code -> user-facing copy (UI_UX_SPECIFICATION §10).
 *
 * Every message says what happened *and* what to do next. Note what is absent:
 * stack traces, internal IDs, and the words "error occurred".
 */
export const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: 'Some of the information provided needs fixing.',
  UNAUTHENTICATED: 'Please sign in to continue.',
  TOKEN_EXPIRED: 'Your session expired. Signing you back in…',
  FORBIDDEN: "You don't have permission to do that.",
  CSRF_FAILED: 'Your session looks stale. Please refresh the page and try again.',
  NOT_FOUND: "We couldn't find that.",
  CONFLICT: 'That already exists.',
  RATE_LIMITED: "You're going a bit fast — try again in a moment.",
  PAYLOAD_TOO_LARGE: 'That request is too large. Try submitting fewer items.',
  UNPROCESSABLE_SOURCE:
    "This link couldn't be processed — it may be private, removed, or unsupported.",
  PLAYLIST_NOT_SUPPORTED:
    "That's a playlist or channel link. Please paste individual video links instead.",
  SOURCE_TOO_LONG: 'This video is longer than the allowed limit. Try a shorter video.',
  LIVE_STREAM_NOT_SUPPORTED:
    "Live streams can't be transcribed. Try again once the recording is published.",
  SOURCE_PRIVATE: "This video is private, so it can't be transcribed.",
  STAGE_TIMEOUT: 'This took too long and was stopped. You can retry it.',
  INSUFFICIENT_STORAGE: 'The server is low on space right now — this will resume automatically.',
  INTERNAL_ERROR: 'Something went wrong on our side. Please try again.',
  NETWORK_ERROR: "We couldn't reach the server. Check your connection and try again.",
};

/** Look up friendly copy for a code, falling back sensibly for unknown ones. */
export function messageForCode(code: string, fallback?: string): string {
  return ERROR_MESSAGES[code] ?? fallback ?? ERROR_MESSAGES.INTERNAL_ERROR!;
}

/**
 * Turn anything thrown into copy safe to show a user.
 *
 * React Query surfaces errors as `unknown`, and a component must never render one
 * directly — a raw message can contain internal detail, or be empty. This is the
 * single funnel every error display goes through.
 */
export function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.userMessage;
  }
  return messageForCode('NETWORK_ERROR');
}

/** A failed API call, carrying everything the UI needs to respond well. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: ApiErrorDetail[];
  /** Shown to the user for support: the one internal ID we do surface. */
  readonly correlationId: string | null;

  constructor(params: {
    code: string;
    message: string;
    status: number;
    details?: ApiErrorDetail[];
    correlationId?: string | null;
  }) {
    super(params.message);
    this.name = 'ApiError';
    this.code = params.code;
    this.status = params.status;
    this.details = params.details ?? [];
    this.correlationId = params.correlationId ?? null;
  }

  /** Copy suitable for showing to a person. */
  get userMessage(): string {
    return messageForCode(this.code, this.message);
  }

  /** True when the access token needs refreshing (handled in Phase 1). */
  get isAuthExpired(): boolean {
    return this.code === 'TOKEN_EXPIRED' || this.status === 401;
  }

  /**
   * Build an ApiError from a failed response.
   *
   * Defensive on purpose: a proxy timeout or a crash before our handlers run can
   * return HTML or nothing at all. In that case we still produce a usable error
   * rather than throwing a JSON parse failure on top of the original problem.
   */
  static async fromResponse(response: Response): Promise<ApiError> {
    let code = 'INTERNAL_ERROR';
    let message = response.statusText || 'Request failed';
    let details: ApiErrorDetail[] = [];
    let correlationId: string | null = response.headers.get('X-Correlation-ID');

    try {
      const body = (await response.json()) as Partial<ApiErrorEnvelope>;
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details ?? [];
        correlationId = body.error.correlation_id ?? correlationId;
      }
    } catch {
      // Not JSON — keep the defaults above.
    }

    return new ApiError({ code, message, status: response.status, details, correlationId });
  }
}
