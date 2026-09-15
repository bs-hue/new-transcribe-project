/**
 * Typed data-fetching hooks.
 *
 * React Query handles caching, retries, and background refetching. Later, job
 * progress will use the same mechanism to poll on an interval and stop
 * automatically once every item reaches a terminal state — which is exactly the
 * logic that goes wrong when hand-written with useEffect.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { apiRequest } from './client';
import type { HealthResponse, PublicConfig } from './types';

/** Query keys are centralised so cache invalidation cannot go out of sync. */
export const queryKeys = {
  health: ['health'] as const,
  publicConfig: ['config', 'public'] as const,
};

/** Backend availability. Used by the home page to report connection status. */
export function useHealth(): UseQueryResult<HealthResponse, Error> {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => apiRequest<HealthResponse>('/health', { signal }),
    // A health check that retries for a long time defeats its own purpose.
    retry: 1,
    staleTime: 15_000,
  });
}

/**
 * Server limits and feature flags.
 *
 * Effectively static for the lifetime of a page load, so it is never refetched
 * on its own — that avoids a needless request on every navigation.
 */
export function usePublicConfig(): UseQueryResult<PublicConfig, Error> {
  return useQuery({
    queryKey: queryKeys.publicConfig,
    queryFn: ({ signal }) => apiRequest<PublicConfig>('/config/public', { signal }),
    staleTime: Infinity,
  });
}
