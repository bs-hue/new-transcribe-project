import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  EmptyState,
  ErrorNotice,
  Pagination,
  PlatformBadge,
  Spinner,
  StatusBadge,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatDate, joinParts, stageLabel } from "@/lib/format";
import type { Job, Paged } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const ALL = "all";

const STATUSES = [
  { value: ALL, label: "All jobs" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

export function JobsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? ALL;

  const [page, setPage] = useState<Paged<Job> | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      setPage(
        await api.jobs(
          {
            status: status === ALL ? undefined : status,
            limit: PAGE_SIZE,
            offset,
          },
          force,
        ),
      );
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load jobs."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [status, offset]);

  useEffect(() => {
    void load(false);
  }, [load]);

  // Keep refreshing only while something is actually moving.
  const busy = (page?.items ?? []).some(
    (job) => job.status === "running" || job.status === "queued",
  );
  useEffect(() => {
    if (!busy) return;
    const handle = setInterval(() => void load(true), 2500);
    return () => clearInterval(handle);
  }, [busy, load]);

  const items = page?.items ?? [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-wrap items-end justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Jobs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every batch submitted, and how it went.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="h-9 gap-1.5 text-xs font-medium"
            title="Reload latest jobs from database"
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", refreshing && "animate-spin text-primary")} />
            <span>{refreshing ? "Reloading…" : "Reload"}</span>
          </Button>
          <Button asChild size="sm" className="h-9">
            <Link to="/jobs/new">Add videos</Link>
          </Button>
        </div>
      </header>

      <Select
        value={status}
        onValueChange={(value) => {
          setOffset(0);
          setParams(value === ALL ? {} : { status: value });
        }}
      >
        <SelectTrigger className="w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUSES.map((s) => (
            <SelectItem key={s.value} value={s.value}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <ErrorNotice message={error} />

      {loading && !page ? (
        <Spinner label="Loading…" />
      ) : items.length === 0 ? (
        <EmptyState
          title={status === ALL ? "No jobs yet" : `No ${status} jobs`}
          description={
            status === ALL
              ? "Submitted batches appear here so you can check how they went."
              : "Try a different filter."
          }
          action={status === ALL ? { to: "/jobs/new", label: "Add videos" } : undefined}
        />
      ) : (
        <Card className="divide-y">
          {items.map((job) => (
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
                  {job.video?.title ?? job.video?.canonical_url ?? "Untitled"}
                </p>
                {job.status === "running" ? (
                  <>
                    <Progress value={job.progress * 100} />
                    <p className="text-xs text-muted-foreground">{stageLabel(job.stage)}</p>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {joinParts(
                      job.submitted_by_name ? `by ${job.submitted_by_name}` : null,
                      formatDate(job.created_at),
                    )}
                  </p>
                )}
                {job.error_message ? (
                  <p className="text-xs text-destructive">{job.error_message}</p>
                ) : null}
              </div>
            </Link>
          ))}
        </Card>
      )}

      <Pagination
        total={page?.total ?? 0}
        limit={PAGE_SIZE}
        offset={offset}
        onChange={setOffset}
        disabled={loading}
      />
    </div>
  );
}
