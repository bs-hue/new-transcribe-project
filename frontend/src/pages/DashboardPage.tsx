import { AlertTriangle, CheckCircle2, Library, Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ErrorNotice,
  PlatformBadge,
  Spinner,
  StatusBadge,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { errorMessage, useAuth } from "@/lib/auth";
import { formatDate, formatDuration, joinParts, stageLabel } from "@/lib/format";
import type { Dashboard } from "@/lib/types";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 2000;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await api.dashboard());
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load the dashboard."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll only while something is actually running, then stop. An idle tab
  // should not hammer the server for numbers that are not changing.
  const busy = (data?.in_progress ?? 0) > 0;
  useEffect(() => {
    if (!busy) return;
    const handle = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(handle);
  }, [busy, load]);

  if (loading) return <Spinner label="Loading…" />;
  if (error && !data) return <ErrorNotice message={error} />;
  if (!data) return null;

  const name = (user?.full_name || user?.email || "").split("@")[0].split(" ")[0];
  const nothingYet = data.total_research === 0 && data.in_progress === 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {greeting()}
            {name ? `, ${name}` : ""}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {new Date().toLocaleDateString(undefined, {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </p>
        </div>
        <Button asChild>
          <Link to="/jobs/new">
            <Plus />
            Add videos
          </Link>
        </Button>
      </header>

      <ErrorNotice message={error} />

      {nothingYet ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Library className="h-8 w-8 text-muted-foreground" />
          <p className="font-medium">No research yet</p>
          <p className="max-w-md text-sm text-muted-foreground">
            Paste your first YouTube or Instagram link and the system will transcribe it,
            file it, and make it searchable.
          </p>
          <Button asChild className="mt-2">
            <Link to="/jobs/new">Add videos</Link>
          </Button>
        </Card>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile
              label="In progress"
              value={data.in_progress}
              to="/jobs?status=running"
              icon={<Loader2 className={cn("h-4 w-4", busy && "animate-spin")} />}
            />
            <Tile
              label="Finished today"
              value={data.finished_today}
              // Jobs finished, so it opens the job list. "Total research" counts
              // videos and opens History; each number leads to what it counted.
              to="/jobs?status=completed"
              icon={<CheckCircle2 className="h-4 w-4" />}
            />
            <Tile
              label="Needs attention"
              value={data.needs_attention}
              to="/jobs?status=failed"
              icon={<AlertTriangle className="h-4 w-4" />}
              alert={data.needs_attention > 0}
            />
            <Tile
              label="Total research"
              value={data.total_research}
              to="/history"
              icon={<Library className="h-4 w-4" />}
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-sm font-semibold">Processing now</h2>
              {data.active_jobs.length > 0 ? (
                <Link to="/jobs" className="text-sm text-primary hover:underline">
                  All jobs
                </Link>
              ) : null}
            </div>

            {data.active_jobs.length === 0 ? (
              <Card className="px-6 py-8 text-center text-sm text-muted-foreground">
                Nothing processing. Add videos to start.
              </Card>
            ) : (
              <Card className="divide-y">
                {data.active_jobs.map((job) => (
                  <Link
                    key={job.id}
                    to={`/jobs/${job.id}`}
                    className="flex items-start gap-4 p-4 hover:bg-accent/40"
                  >
                    <Thumbnail
                      src={job.video?.thumbnail_url}
                      alt={job.video?.title ?? "Video"}
                      className="h-14 w-24"
                    />
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={job.status} />
                        <PlatformBadge platform={job.video?.platform} />
                      </div>
                      <p className="truncate text-sm font-medium">
                        {job.video?.title ?? job.video?.canonical_url ?? "Reading details…"}
                      </p>
                      <Progress value={job.progress * 100} />
                      <p className="text-xs text-muted-foreground">{stageLabel(job.stage)}</p>
                    </div>
                  </Link>
                ))}
              </Card>
            )}
          </section>

          {data.recent_transcripts.length > 0 ? (
            <section className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-sm font-semibold">Recent research</h2>
                <Link to="/history" className="text-sm text-primary hover:underline">
                  See all
                </Link>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.recent_transcripts.map((item) => (
                  <Link key={item.id} to={`/history/${item.video_id}`}>
                    <Card className="h-full p-4 transition-colors hover:bg-accent/40">
                      <div className="flex gap-3">
                        <Thumbnail
                          src={item.video?.thumbnail_url}
                          alt={item.video?.title ?? "Video"}
                          className="h-12 w-20"
                        />
                        <div className="min-w-0 flex-1 space-y-1">
                          <PlatformBadge platform={item.video?.platform} />
                          <p className="truncate text-sm font-medium">
                            {item.video?.title ?? "Untitled"}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {joinParts(
                              item.video?.author,
                              formatDuration(item.duration_seconds),
                              formatDate(item.created_at),
                            )}
                          </p>
                        </div>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  to,
  icon,
  alert = false,
}: {
  label: string;
  value: number;
  to: string;
  icon: React.ReactNode;
  alert?: boolean;
}) {
  return (
    <Link to={to}>
      <Card
        className={cn(
          "h-full transition-colors hover:bg-accent/40",
          // Only one tile is ever coloured, and only when it needs a person.
          alert && "border-warning/50 bg-warning/5",
        )}
      >
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </CardTitle>
          <span className={cn("text-muted-foreground", alert && "text-warning")}>{icon}</span>
        </CardHeader>
        <CardContent>
          <p
            className={cn(
              "text-3xl font-semibold tabular-nums tracking-tight",
              alert && "text-warning",
            )}
          >
            {value}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}
