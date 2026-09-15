/**
 * The one place this application talks to the network.
 *
 * Components never call `fetch`; they use the typed hooks in `hooks.ts`, which
 * call this. The payoff is that authentication, error shape, and credential
 * handling are implemented once instead of being re-derived (slightly
 * differently) in every feature.
 */

import { API_BASE_URL } from '@/config/env';

import { ApiError } from './errors';

/**
 * The access token, held in a module variable — that is, in memory only.
 *
 * Deliberately NOT in localStorage: anything stored there is readable by any
 * script that manages to run on the page, which turns a cross-site scripting bug
 * into a stolen credential. In memory, the token dies with the tab, and the
 * long-lived refresh token lives in an HttpOnly cookie that JavaScript cannot
 * read at all (TECHNOLOGY_DECISIONS §5).
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Perform an API request and return the parsed response.
 *
 * @throws ApiError for any non-2xx response, or for a network failure.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options;

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Sends and accepts the refresh-token cookie (Phase 1).
      credentials: 'include',
      signal,
    });
  } catch (cause) {
    // The server was unreachable, or the request was aborted. There is no
    // response to parse, so synthesise an error in the same shape as any other.
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: cause instanceof Error ? cause.message : 'Network request failed',
      status: 0,
    });
  }

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  // 204 No Content has no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
