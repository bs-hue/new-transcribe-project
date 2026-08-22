import { ArrowLeft, Copy, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ExportMenu } from "@/components/ExportMenu";
import { ErrorNotice, PlatformBadge, Spinner, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatDate, formatDuration, formatTimecode, joinParts, stageLabel } from "@/lib/format";
import type { VideoDetail } from "@/lib/types";

export function TranscriptPage() {
  const { videoId = "" } = useParams();
  const navigate = useNavigate();

  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setVideo(await api.video(videoId));
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load this video."));
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    void load();
  }, [load]);

  // A job still in flight means the transcript is on its way; keep refreshing.
  const pending =
    video?.latest_job?.status === "queued" || video?.latest_job?.status === "running";

  useEffect(() => {
    if (!pending) return;
    const handle = setInterval(() => void load(), 2500);
    return () => clearInterval(handle);
  }, [pending, load]);

  async function copy() {
    if (!video?.transcript) return;
    await navigator.clipboard.writeText(video.transcript.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function remove() {
    if (!confirm("Delete this video and its transcript? This cannot be undone.")) return;
    try {
      await api.deleteVideo(videoId);
      navigate("/history");
    } catch (err) {
      setError(errorMessage(err, "Could not delete this video."));
    }
  }

  if (loading) return <Spinner label="Loading…" />;
  if (error && !video) return <ErrorNotice message={error} />;
  if (!video) return null;

  const transcript = video.transcript;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Button asChild variant="ghost" size="sm" className="-ml-3">
        <Link to="/history">
          <ArrowLeft />
          Back to history
        </Link>
      </Button>

      <ErrorNotice message={error} />

      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-4 space-y-0">
          <div className="min-w-0 space-y-2">
            <PlatformBadge platform={video.platform} />
            <h1 className="text-xl font-semibold tracking-tight">
              {video.title ?? "Untitled"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {joinParts(
                video.author,
                formatDuration(video.duration_seconds),
                video.published_at ? `Published ${formatDate(video.published_at)}` : null,
                transcript ? `${transcript.word_count} words` : null,
              )}
            </p>
            <a
              href={video.canonical_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block break-all text-xs text-primary hover:underline"
            >
              {video.canonical_url}
            </a>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {transcript ? (
              <>
                <Button variant="outline" onClick={copy}>
                  <Copy />
                  {copied ? "Copied" : "Copy text"}
                </Button>
                <ExportMenu
                  transcriptId={transcript.id}
                  hasSegments={transcript.segments.length > 0}
                />
              </>
            ) : null}
            <Button variant="ghost" size="icon" onClick={remove} title="Delete">
              <Trash2 />
            </Button>
          </div>
        </CardHeader>
      </Card>

      {!transcript ? (
        <JobStatusPanel job={video.latest_job} onRetried={load} />
      ) : (
        <Card>
          <Tabs defaultValue="full">
            <div className="flex items-center justify-between gap-4 border-b p-4">
              <TabsList>
                <TabsTrigger value="full">Full text</TabsTrigger>
                <TabsTrigger value="timed" disabled={transcript.segments.length === 0}>
                  Timed segments
                </TabsTrigger>
              </TabsList>
              <span className="text-xs text-muted-foreground">
                {joinParts(transcript.provider, transcript.language)}
              </span>
            </div>

            <TabsContent value="full">
              <CardContent className="whitespace-pre-wrap p-6 text-sm leading-7">
                {transcript.text}
              </CardContent>
            </TabsContent>

            <TabsContent value="timed">
              <ol className="divide-y">
                {transcript.segments.map((segment) => (
                  <li key={segment.index} className="flex gap-4 px-6 py-3">
                    <span className="w-14 shrink-0 pt-0.5 font-mono text-xs text-muted-foreground">
                      {formatTimecode(segment.start)}
                    </span>
                    <span className="text-sm leading-6">{segment.text}</span>
                  </li>
                ))}
              </ol>
            </TabsContent>
          </Tabs>
        </Card>
      )}
    </div>
  );
}

function JobStatusPanel({
  job,
  onRetried,
}: {
  job: VideoDetail["latest_job"];
  onRetried: () => void;
}) {
  if (!job) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No transcript yet for this video.
      </Card>
    );
  }

  return (
    <Card className="space-y-3 p-8 text-center">
      <div className="flex justify-center">
        <StatusBadge status={job.status} />
      </div>
      <p className="text-sm">
        {job.status === "failed"
          ? "This video could not be transcribed."
          : `${stageLabel(job.stage)}…`}
      </p>
      {job.error_message ? (
        <p className="text-sm text-destructive">{job.error_message}</p>
      ) : null}
      {job.status === "failed" ? (
        <Button variant="outline" onClick={() => api.retryJob(job.id).then(onRetried)}>
          Try again
        </Button>
      ) : null}
    </Card>
  );
}
