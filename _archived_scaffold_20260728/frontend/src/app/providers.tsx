import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

/**
 * Application-wide providers.
 *
 * The query client accepts an override so tests can supply one with retries
 * disabled — otherwise a test asserting an error state would wait for retry
 * backoff before the assertion could pass.
 */
function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // One retry absorbs a transient blip without making a genuine failure
        // take ages to surface.
        retry: 1,
        // Refetching on every window focus is wasted work against a small
        // server. Progress polling asks explicitly where it is needed.
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
}

interface AppProvidersProps {
  children: ReactNode;
  client?: QueryClient;
}

export function AppProviders({ children, client }: AppProvidersProps) {
  // useState so the client is created once per mount, not on every render.
  const [queryClient] = useState(() => client ?? createQueryClient());

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
