import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { toUserMessage } from '@/shared/lib/api/errors';
import { useHealth, usePublicConfig } from '@/shared/lib/api/hooks';
import { Button } from '@/shared/ui/button';

/**
 * Phase 0's visible outcome: proof that the website and the API talk to each
 * other, and that configuration flows from the server to the UI.
 *
 * Modest on purpose. Phase 3 replaces it with the real dashboard — but every
 * async surface here already handles all four states (loading, error, empty,
 * success), which is the standard every screen after this one must meet.
 */
export function HomePage() {
  const health = useHealth();
  const config = usePublicConfig();

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Bulk Transcript Agent</h1>
        <p className="text-sm text-muted-foreground">
          Foundation is in place. The transcription pipeline arrives in Phase 2.
        </p>
      </header>

      <section aria-labelledby="connection-heading" className="rounded-lg border bg-card p-5">
        <h2 id="connection-heading" className="mb-4 text-sm font-medium">
          API connection
        </h2>

        {health.isPending && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            Checking…
          </p>
        )}

        {health.isError && (
          <div className="space-y-3" role="alert">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle aria-hidden="true" className="size-4" />
              {toUserMessage(health.error)}
            </p>
            <p className="text-xs text-muted-foreground">
              Is the backend running? Start it with <code>./scripts/dev-backend.ps1</code>
            </p>
            <Button size="sm" variant="outline" onClick={() => void health.refetch()}>
              Try again
            </Button>
          </div>
        )}

        {health.isSuccess && (
          <div className="space-y-2">
            <p className="flex items-center gap-2 text-sm">
              <CheckCircle2 aria-hidden="true" className="size-4 text-success" />
              <span className="font-medium">Connected</span>
              <span className="text-muted-foreground">— version {health.data.version}</span>
            </p>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {Object.entries(health.data.checks).map(([name, status]) => (
                <li key={name}>
                  {name}: <span className="font-medium">{status}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section aria-labelledby="limits-heading" className="rounded-lg border bg-card p-5">
        <h2 id="limits-heading" className="mb-4 text-sm font-medium">
          Server limits
        </h2>

        {config.isSuccess ? (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Stat label="URLs per batch" value={String(config.data.max_urls_per_batch)} />
            <Stat
              label="Max video length"
              value={`${Math.round(config.data.max_video_duration_seconds / 3600)} hours`}
            />
            <Stat label="Default model" value={config.data.default_model} />
            <Stat label="Retry attempts" value={String(config.data.max_attempts)} />
            <Stat
              label="Formats"
              value={config.data.supported_formats.join(', ').toUpperCase()}
            />
            <Stat
              label="AI summaries"
              value={config.data.summarize_available ? 'Available' : 'Disabled'}
            />
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">
            {config.isError ? toUserMessage(config.error) : 'Loading…'}
          </p>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
