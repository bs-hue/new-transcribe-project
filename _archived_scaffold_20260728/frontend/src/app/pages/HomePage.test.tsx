import { QueryClient } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { HomePage } from '@/app/pages/HomePage';
import { AppProviders } from '@/app/providers';

const HEALTH_OK = {
  status: 'ok',
  version: '0.1.0',
  checks: { db: 'ok', queue: 'ok' },
};

const PUBLIC_CONFIG = {
  summarize_available: false,
  max_urls_per_batch: 25,
  max_video_duration_seconds: 7200,
  supported_formats: ['txt', 'srt', 'vtt', 'json'],
  default_model: 'small',
  available_models: ['tiny', 'base', 'small', 'medium'],
  manual_retry_enabled: true,
  max_attempts: 3,
  playlists_supported: false,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderHomePage() {
  // Retries off: otherwise asserting an error state means waiting out backoff.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return render(
    <AppProviders client={client}>
      <HomePage />
    </AppProviders>,
  );
}

describe('HomePage', () => {
  it('reports a healthy connection and renders the server limits', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/health')) return Promise.resolve(jsonResponse(HEALTH_OK));
        if (url.includes('/config/public')) return Promise.resolve(jsonResponse(PUBLIC_CONFIG));
        return Promise.resolve(new Response(null, { status: 404 }));
      }),
    );

    renderHomePage();

    expect(await screen.findByText(/connected/i)).toBeInTheDocument();
    expect(await screen.findByText('25')).toBeInTheDocument();
    expect(await screen.findByText('2 hours')).toBeInTheDocument();
  });

  it('hides AI summaries when the server has no key configured', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/health')) return Promise.resolve(jsonResponse(HEALTH_OK));
        return Promise.resolve(jsonResponse(PUBLIC_CONFIG));
      }),
    );

    renderHomePage();

    expect(await screen.findByText('Disabled')).toBeInTheDocument();
  });

  it('shows friendly guidance when the API cannot be reached', async () => {
    // The most common failure while developing: the frontend is up, the backend
    // is not. The page should say so plainly and suggest the fix.
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('ECONNREFUSED'))));

    renderHomePage();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/couldn't reach the server/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});
