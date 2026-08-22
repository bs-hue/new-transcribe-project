import { AlertTriangle, ArrowRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNotice, PlatformBadge, Thumbnail } from "@/components/shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatBytes, formatDuration, joinParts, splitUrls } from "@/lib/format";
import type { Meta, Preview } from "@/lib/types";
import { cn } from "@/lib/utils";

type Step = "input" | "review";

// The third step happens on the Job Details screen; it is shown here only so
// the user can see where they are in the whole flow.
const STEPS: { key: Step | "transcribe"; label: string }[] = [
  { key: "input", label: "Paste URLs" },
  { key: "review", label: "Review" },
  { key: "transcribe", label: "Transcribe" },
];

export function NewJobPage() {
  const navigate = useNavigate();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [step, setStep] = useState<Step>("input");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [previews, setPreviews] = useState<Preview[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Capabilities come from the server so the UI never hardcodes limits.
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const urls = splitUrls(text);
  const maxUrls = meta?.limits.max_urls_per_request ?? 50;

  const check = useCallback(async () => {
    setError(null);
    if (urls.length === 0) {
      setError("Paste at least one YouTube, Instagram, or Meta Ads Library URL.");
      return;
    }
    if (urls.length > maxUrls) {
      setError(`You pasted ${urls.length} URLs. The limit is ${maxUrls} per batch.`);
      return;
    }

    setBusy(true);
    try {
      const { results } = await api.preview(urls);
      setPreviews(results);
      setSelected(new Set(results.filter((p) => p.valid && p.within_limits).map((p) => p.url)));
      setStep("review");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [urls, maxUrls]);

  const start = useCallback(async () => {
    setError(null);
    const chosen = previews.filter((p) => selected.has(p.url)).map((p) => p.url);
    if (chosen.length === 0) {
      setError("Select at least one video to transcribe.");
      return;
    }

    setBusy(true);
    try {
      const submission = await api.submit(chosen);
      const firstJob = submission.results.find((r) => r.accepted)?.job_id;
      if (firstJob) {
        navigate(`/jobs/${firstJob}`);
      } else {
        navigate("/jobs");
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [previews, selected, navigate]);

  const toggle = useCallback((url: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }, []);

  const currentStep = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <header className="space-y-1">
        <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Add videos to research</h1>
        <p className="text-sm text-muted-foreground">
          Paste the links. The system reads each video&apos;s details, downloads it,
          transcribes it, and files it in the library — searchable and exportable.
        </p>
      </header>

      <ol className="flex flex-wrap items-center gap-2 text-sm">
        {STEPS.map((s, index) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold",
                index <= currentStep
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {index + 1}
            </span>
            <span className={index <= currentStep ? "font-medium" : "text-muted-foreground"}>
              {s.label}
            </span>
            {index < STEPS.length - 1 ? (
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
            ) : null}
          </li>
        ))}
      </ol>

      <ErrorNotice message={error} />

      {step === "input" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Paste video URLs</CardTitle>
            <p className="text-sm text-muted-foreground">
              One per line. YouTube, Instagram Reels, and Meta / Facebook Ads Library links (up to {maxUrls} at a time).
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={9}
              spellCheck={false}
              placeholder={
                "https://www.youtube.com/watch?v=…\nhttps://www.instagram.com/reel/…\nhttps://www.facebook.com/ads/library/?id=…"
              }
              className="resize-y font-mono text-xs leading-relaxed"
            />

            <div className="flex items-center justify-between gap-4">
              <span className="text-xs text-muted-foreground">
                {urls.length} URL{urls.length === 1 ? "" : "s"} detected
              </span>
              <Button onClick={check} disabled={busy}>
                {busy ? "Checking…" : "Check videos"}
              </Button>
            </div>

            {meta && !meta.transcription_ready ? (
              <Alert variant="warning">
                <AlertTriangle />
                <AlertDescription>
                  Transcription is not configured: {meta.transcription_error}
                </AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {step === "review" ? (
        <ReviewStep
          previews={previews}
          selected={selected}
          onToggle={toggle}
          onBack={() => setStep("input")}
          onStart={start}
          busy={busy}
        />
      ) : null}

    </div>
  );
}

function ReviewStep({
  previews,
  selected,
  onToggle,
  onBack,
  onStart,
  busy,
}: {
  previews: Preview[];
  selected: Set<string>;
  onToggle: (url: string) => void;
  onBack: () => void;
  onStart: () => void;
  busy: boolean;
}) {
  const usable = previews.filter((p) => p.valid && p.within_limits);
  const problems = previews.length - usable.length;

  return (
    <section className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">Review before transcribing</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {usable.length} ready · {problems} cannot be processed · nothing has been
              downloaded yet
            </p>
          </div>
          <span className="text-sm text-muted-foreground">{selected.size} selected</span>
        </CardHeader>

        <div className="divide-y border-t">
          {previews.map((preview) => (
            <PreviewRow
              key={preview.url}
              preview={preview}
              checked={selected.has(preview.url)}
              onToggle={() => onToggle(preview.url)}
            />
          ))}
        </div>
      </Card>

      <div className="flex items-center justify-between gap-4">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onStart} disabled={busy || selected.size === 0}>
          {busy
            ? "Starting…"
            : `Transcribe ${selected.size} video${selected.size === 1 ? "" : "s"}`}
        </Button>
      </div>
    </section>
  );
}

function PreviewRow({
  preview,
  checked,
  onToggle,
}: {
  preview: Preview;
  checked: boolean;
  onToggle: () => void;
}) {
  const selectable = preview.valid && preview.within_limits;

  return (
    <div className="flex items-start gap-4 p-4">
      <Checkbox
        checked={checked}
        onCheckedChange={onToggle}
        disabled={!selectable}
        className="mt-1"
        aria-label={`Select ${preview.title ?? preview.url}`}
      />
      <Thumbnail src={preview.thumbnail_url} alt={preview.title ?? "Video thumbnail"} />

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <PlatformBadge platform={preview.platform} />
          {preview.already_transcribed ? (
            <span className="text-xs text-muted-foreground">Already in library</span>
          ) : null}
        </div>

        <p className="truncate text-sm font-medium">{preview.title ?? preview.url}</p>

        {preview.valid ? (
          <p className="text-xs text-muted-foreground">
            {joinParts(
              preview.author,
              preview.duration_seconds != null
                ? formatDuration(preview.duration_seconds)
                : null,
              preview.estimated_size_bytes != null
                ? `~${formatBytes(preview.estimated_size_bytes)}`
                : null,
            )}
          </p>
        ) : (
          <p className="text-xs text-destructive">{preview.error_message}</p>
        )}

        {preview.limit_reasons.map((reason) => (
          <p key={reason} className="text-xs text-destructive">
            {reason}
          </p>
        ))}
        {preview.warnings.map((warning) => (
          <p key={warning} className="text-xs text-warning">
            {warning}
          </p>
        ))}
      </div>
    </div>
  );
}

