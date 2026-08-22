import { ArrowLeft, Check, ChevronRight, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExportMenu } from "@/components/ExportMenu";
import {
  ErrorNotice,
  PlatformBadge,
  Spinner,
  StatusBadge,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatDate, joinParts, stageLabel } from "@/lib/format";
import type { BatchStatus, Job, TranscriptDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The pipeline, in order. Shown as a track so a failure is visibly located
 *  rather than described — "it stopped at Downloading" reads instantly. */
const STAGES = [
  "fetching_metadata",
  "checking_limits",
  "downloading",
  "extracting_audio",
  "transcribing",
  "storing",
] as const;

const POLL_INTERVAL_MS = 2000;

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [transcripts, setTranscripts] = useState<Record<string, TranscriptDetail>>({});

  const load = useCallback(async () => {
    try {
      const current = await api.job(jobId);
      setJob(current);
      // A job belongs to a batch, and a person thinks in batches — so show the
      // whole submission, with this job's own row highlighted.
      setBatch(current.batch_id ? await api.batchStatus(current.batch_id) : null);
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load this job."));
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = batch ? batch.queued > 0 || batch.running > 0 : false;
  useEffect(() => {
    if (!active) return;
    const handle = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(handle);
  }, [active, load]);

  // The batch screen is where someone lands after pasting a block of links, so
  // the finished scripts belong here rather than seven clicks away.
  const finished = useMemo(() => {
    const all = batch?.jobs ?? (job ? [job] : []);
    return all.filter((row) => row.status === "completed" && row.transcript_id);
  }, [batch, job]);

  const transcriptIds = useMemo(
    () => finished.map((row) => row.transcript_id as string),
    [finished],
  );

  useEffect(() => {
    const missing = transcriptIds.filter((id) => !(id in transcripts));
    if (missing.length === 0) return;

    let abandoned = false;
    // One failure should not blank the others, so each is caught on its own.
    void Promise.all(missing.map((id) => api.transcript(id).catch(() => null))).then(
      (loaded) => {
        if (abandoned) return;
        setTranscripts((current) => {
          const next = { ...current };
          for (const detail of loaded) if (detail) next[detail.id] = detail;
          return next;
        });
      },
    );
    return () => {
      abandoned = true;
    };
  }, [transcriptIds, transcripts]);

  async function retry(id: string) {
    try {
      await api.retryJob(id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function cancel(id: string) {
    try {
      await api.cancelJob(id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (loading) return <Spinner label="Loading…" />;
  if (error && !job) return <ErrorNotice message={error} />;
  if (!job) return null;

  const rows = batch?.jobs ?? [job];
  const done = batch ? batch.completed + batch.failed + batch.cancelled : 0;
  const overall = batch && batch.total ? (done / batch.total) * 100 : 0;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Button asChild variant="ghost" size="sm" className="-ml-3">
        <Link to="/jobs">
          <ArrowLeft />
          Back to jobs
        </Link>
      </Button>

      <ErrorNotice message={error} />

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                {batch && batch.total > 1 ? `Batch of ${batch.total} videos` : "Job"}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {joinParts(
                  job.submitted_by_name ? `Submitted by ${job.submitted_by_name}` : null,
                  formatDate(job.created_at),
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {batch ? (
                <div className="text-right">
                  <p className="text-sm font-medium">
                    {done} of {batch.total} finished
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {batch.completed} succeeded · {batch.failed} failed
                  </p>
                </div>
              ) : null}
              {transcriptIds.length > 0 ? (
                <ExportMenu
                  transcriptIds={transcriptIds}
                  label={transcriptIds.length > 1 ? "Download all" : "Download"}
                  variant="default"
                  hasSegments={finished.length > 0}
                />
              ) : null}
            </div>
          </div>
          {batch ? <Progress value={overall} /> : null}
        </CardHeader>

        <div className="divide-y border-t">
          {rows.map((row) => (
            <JobRow
              key={row.id}
              job={row}
              highlighted={row.id === job.id && rows.length > 1}
              onRetry={() => retry(row.id)}
              onCancel={() => cancel(row.id)}
            />
          ))}
        </div>
      </Card>

      {finished.length > 0 ? (
        <Results jobs={finished} transcripts={transcripts} />
      ) : null}
    </div>
  );
}

/** Every finished script, stacked. Collapsed by default so a batch of seven
 *  stays scannable, and the first one opens because a batch of one should not
 *  need a click to show the thing it was submitted for. */
function Results({
  jobs,
  transcripts,
}: {
  jobs: Job[];
  transcripts: Record<string, TranscriptDetail>;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  return (
    <Card>
      <CardHeader className="pb-3">
        <h2 className="text-lg font-semibold tracking-tight">
          {jobs.length > 1 ? `${jobs.length} transcripts` : "Transcript"}
        </h2>
        <p className="text-sm text-muted-foreground">
          Read them here, or download the whole batch as one file above.
        </p>
      </CardHeader>

      <div className="divide-y border-t">
        {jobs.map((job, index) => {
          const transcript = transcripts[job.transcript_id as string];
          const expanded = open[job.id] ?? (jobs.length === 1 && index === 0);
          return (
            <div key={job.id} className="p-4">
              <button
                type="button"
                className="flex w-full items-center gap-2 text-left"
                onClick={() => setOpen((current) => ({ ...current, [job.id]: !expanded }))}
              >
                <ChevronRight
                  className={cn("h-4 w-4 shrink-0 transition-transform", expanded && "rotate-90")}
                />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {index + 1}. {job.video?.title ?? "Untitled"}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {transcript ? `${transcript.word_count.toLocaleString()} words` : "loading…"}
                </span>
              </button>

              {expanded ? (
                transcript ? (
                  <div className="mt-3 space-y-3 pl-6">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">
                      {transcript.text || "(no speech detected)"}
                    </p>
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/history/${job.video_id}`}>Open full transcript</Link>
                    </Button>
                  </div>
                ) : (
                  <p className="mt-3 pl-6 text-sm text-muted-foreground">Loading…</p>
                )
              ) : null}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function JobRow({
  job,
  highlighted,
  onRetry,
  onCancel,
}: {
  job: Job;
  highlighted: boolean;
  onRetry: () => void;
  onCancel: () => void;
}) {
  const currentIndex = STAGES.indexOf(job.stage as (typeof STAGES)[number]);
  const finished = job.status === "completed";
  const failed = job.status === "failed";

  return (
    <div className={cn("space-y-3 p-4", highlighted && "bg-accent/40")}>
      <div className="flex items-start gap-4">
        <Thumbnail
          src={job.video?.thumbnail_url}
          alt={job.video?.title ?? "Video"}
          className="h-14 w-24"
        />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={job.status} />
            <PlatformBadge platform={job.video?.platform} />
            {job.attempts > 1 ? (
              <span className="text-xs text-muted-foreground">
                attempt {job.attempts}
              </span>
            ) : null}
          </div>
          <p className="truncate text-sm font-medium">
            {job.video?.title ?? job.video?.canonical_url ?? "Reading details…"}
          </p>
          {job.error_message ? (
            <p className="text-sm text-destructive">{job.error_message}</p>
          ) : null}
        </div>

        <div className="flex shrink-0 gap-2">
          {finished && job.video_id ? (
            <Button asChild variant="outline" size="sm">
              <Link to={`/history/${job.video_id}`}>Open transcript</Link>
            </Button>
          ) : null}
          {failed || job.status === "cancelled" ? (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RotateCcw />
              Try again
            </Button>
          ) : null}
          {job.status === "queued" ? (
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X />
              Cancel
            </Button>
          ) : null}
        </div>
      </div>

      {/* The stage track. Hidden once done — a finished job needs no map. */}
      {finished ? null : (
        <ol className="flex flex-wrap gap-x-4 gap-y-1.5 pl-28 text-xs">
          {STAGES.map((stage, index) => {
            const passed = currentIndex > index;
            const current = currentIndex === index && job.status === "running";
            const stalled = failed && currentIndex === index;
            return (
              <li
                key={stage}
                className={cn(
                  "flex items-center gap-1.5",
                  passed && "text-muted-foreground",
                  current && "font-medium text-primary",
                  stalled && "font-medium text-destructive",
                  !passed && !current && !stalled && "text-muted-foreground/50",
                )}
              >
                {passed ? (
                  <Check className="h-3 w-3" />
                ) : stalled ? (
                  <X className="h-3 w-3" />
                ) : (
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      current ? "bg-primary" : "bg-current opacity-40",
                    )}
                  />
                )}
                {stageLabel(stage)}
              </li>
            );
          })}
        </ol>
      )}

      {job.status === "running" ? (
        <div className="pl-28">
          <Progress value={job.progress * 100} />
        </div>
      ) : null}
    </div>
  );
}
