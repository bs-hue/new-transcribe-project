import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Clock,
  FileAudio,
  FileText,
  FolderPlus,
  History,
  Layers,
  Library,
  Loader2,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  User,
  Video,
  Zap,
} from "lucide-react";
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

const POLL_INTERVAL_MS = 2500;

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
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      setData(await api.dashboard(force));
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load the dashboard."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  // Poll only while something is actually running, then stop.
  const busy = (data?.in_progress ?? 0) > 0;
  useEffect(() => {
    if (!busy) return;
    const handle = setInterval(() => void load(true), POLL_INTERVAL_MS);
    return () => clearInterval(handle);
  }, [busy, load]);

  if (loading && !data) return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner label="Loading dashboard…" />
    </div>
  );
  if (error && !data) return <ErrorNotice message={error} />;
  if (!data) return null;

  const name = (user?.full_name || user?.email || "").split("@")[0].split(" ")[0];
  const nothingYet = data.total_research === 0 && data.in_progress === 0;

  const formattedDate = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Greeting & Action Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div className="space-y-1">
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            {greeting()}{name ? `, ${name}` : ""}
          </h1>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5" />
            <span>{formattedDate}</span>
            <span>·</span>
            <span className="flex items-center gap-1">
              <span className={cn("h-1.5 w-1.5 rounded-full", busy ? "bg-primary animate-pulse" : "bg-success")} />
              {busy ? "Transcribing in background" : "System ready"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap sm:shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="h-8 sm:h-9 gap-1.5 text-xs font-medium"
            title="Reload latest data from database"
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", refreshing && "animate-spin text-primary")} />
            <span>{refreshing ? "Reloading…" : "Reload"}</span>
          </Button>

          <Button asChild variant="outline" size="sm" className="h-8 sm:h-9 gap-1.5 text-xs font-medium">
            <Link to="/search">
              <Search className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Search</span>
            </Link>
          </Button>

          <Button asChild size="sm" className="h-8 sm:h-9 gap-1.5 text-xs font-medium shadow-sm">
            <Link to="/jobs/new">
              <Plus className="h-3.5 w-3.5" />
              <span>Add Videos</span>
            </Link>
          </Button>
        </div>
      </header>

      <ErrorNotice message={error} />

      {nothingYet ? (
        /* Rich Onboarding Hero when there is no research */
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-10 text-center relative overflow-hidden shadow-sm">
          <div className="max-w-md mx-auto space-y-4 relative z-10">
            <div className="mx-auto flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-inner">
              <PlayCircle className="h-6 w-6 sm:h-7 sm:w-7" />
            </div>

            <div className="space-y-2">
              <h2 className="font-heading text-lg sm:text-2xl font-bold tracking-tight text-foreground">
                Start your research library
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                Paste any YouTube video or Instagram Reel URL to automatically download, extract audio, and generate accurate timestamps & transcripts.
              </p>
            </div>

            <div className="pt-2">
              <Button asChild size="default" className="rounded-xl px-5 sm:px-6 gap-2 shadow-sm font-medium">
                <Link to="/jobs/new">
                  <Plus className="h-4 w-4" />
                  <span>Transcribe First Video</span>
                </Link>
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Key Metric Tiles */}
          <section className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-4">
            <MetricCard
              label="In Progress"
              value={data.in_progress}
              to="/jobs?status=running"
              icon={<Loader2 className={cn("h-3.5 w-3.5 sm:h-4 sm:w-4", busy && "animate-spin text-primary")} />}
              subtitle="Active tasks"
              variant={data.in_progress > 0 ? "active" : "default"}
            />
            <MetricCard
              label="Finished Today"
              value={data.finished_today}
              to="/jobs?status=completed"
              icon={<CheckCircle2 className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-emerald-500" />}
              subtitle="Completed today"
              variant="default"
            />
            <MetricCard
              label="Needs Attention"
              value={data.needs_attention}
              to="/jobs?status=failed"
              icon={<AlertTriangle className={cn("h-3.5 w-3.5 sm:h-4 sm:w-4", data.needs_attention > 0 ? "text-amber-500" : "text-muted-foreground")} />}
              subtitle="Requires review"
              variant={data.needs_attention > 0 ? "warning" : "default"}
            />
            <MetricCard
              label="Total Research"
              value={data.total_research}
              to="/history"
              icon={<Library className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />}
              subtitle="Archived videos"
              variant="default"
            />
          </section>

          {/* Active Processing Section */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-sm sm:text-base font-semibold text-foreground">
                  Processing Now
                </h2>
                {data.active_jobs.length > 0 && (
                  <span className="inline-flex items-center justify-center px-2 py-0.5 text-xs font-semibold rounded-full bg-primary/10 text-primary">
                    {data.active_jobs.length}
                  </span>
                )}
              </div>

              {data.active_jobs.length > 0 && (
                <Link
                  to="/jobs"
                  className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
                >
                  <span>All jobs</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              )}
            </div>

            {data.active_jobs.length === 0 ? (
              <Card className="p-5 sm:p-6 text-center border border-dashed border-border/80 bg-muted/20">
                <div className="flex flex-col items-center gap-1 text-muted-foreground">
                  <Clock className="h-4 w-4 sm:h-5 sm:w-5 text-muted-foreground/60" />
                  <p className="text-xs font-medium">No videos currently processing</p>
                  <p className="text-[11px] text-muted-foreground/80">
                    Queue new jobs anytime from the Add Videos page
                  </p>
                </div>
              </Card>
            ) : (
              <Card className="divide-y divide-border/60 overflow-hidden shadow-sm">
                {data.active_jobs.map((job) => (
                  <Link
                    key={job.id}
                    to={`/jobs/${job.id}`}
                    className="flex flex-col sm:flex-row sm:items-center gap-3 p-3.5 sm:p-4 transition-colors hover:bg-muted/40 group"
                  >
                    <div className="relative shrink-0">
                      <Thumbnail
                        src={job.video?.thumbnail_url}
                        alt={job.video?.title ?? "Video"}
                        className="h-16 w-28 rounded-lg shadow-sm"
                      />
                      {job.video?.platform && (
                        <div className="absolute top-1 left-1">
                          <PlatformBadge platform={job.video.platform} />
                        </div>
                      )}
                    </div>

                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-xs sm:text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                          {job.video?.title ?? job.video?.canonical_url ?? "Untitled Video"}
                        </p>
                        <StatusBadge status={job.status} />
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>{stageLabel(job.stage)}</span>
                          <span className="font-mono">{Math.round(job.progress * 100)}%</span>
                        </div>
                        <Progress value={job.progress * 100} className="h-1.5" />
                      </div>
                    </div>
                  </Link>
                ))}
              </Card>
            )}
          </section>

          {/* Recent Transcripts Section */}
          {data.recent_transcripts.length > 0 && (
            <section className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="font-heading text-sm sm:text-base font-semibold text-foreground">
                    Recent Research
                  </h2>
                  <span className="text-xs text-muted-foreground font-normal">
                    ({data.recent_transcripts.length} latest)
                  </span>
                </div>

                <Link
                  to="/history"
                  className="text-xs font-medium text-primary hover:underline flex items-center gap-1"
                >
                  <span>See full archive</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-5">
                {data.recent_transcripts.map((item) => (
                  <Link
                    key={item.id}
                    to={`/history/${item.video_id}`}
                    className="group focus:outline-none"
                  >
                    <Card className="h-full overflow-hidden border border-border/80 bg-card transition-all duration-200 hover:border-primary/50 hover:shadow-md flex flex-col justify-between">
                      {/* Thumbnail Container with overlays */}
                      <div className="relative aspect-video w-full bg-muted overflow-hidden">
                        <Thumbnail
                          src={item.video?.thumbnail_url}
                          alt={item.video?.title ?? "Video"}
                          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                        />

                        {/* Top Platform Overlay */}
                        {item.video?.platform && (
                          <div className="absolute top-2 left-2 z-10">
                            <PlatformBadge platform={item.video.platform} />
                          </div>
                        )}

                        {/* Duration Overlay */}
                        {item.duration_seconds ? (
                          <div className="absolute bottom-2 right-2 rounded-md bg-black/80 px-1.5 py-0.5 text-[10px] sm:text-[11px] font-semibold text-white backdrop-blur-sm">
                            {formatDuration(item.duration_seconds)}
                          </div>
                        ) : null}
                      </div>

                      {/* Content Info */}
                      <CardContent className="p-3.5 sm:p-4 flex-1 flex flex-col justify-between space-y-3">
                        <div className="space-y-1">
                          <h3 className="font-heading font-medium text-xs sm:text-sm leading-snug line-clamp-2 text-foreground group-hover:text-primary transition-colors">
                            {item.video?.title ?? "Untitled Video"}
                          </h3>

                          {item.video?.author && (
                            <p className="text-[11px] sm:text-xs text-muted-foreground line-clamp-1 flex items-center gap-1">
                              <User className="h-3 w-3 shrink-0" />
                              <span>{item.video.author}</span>
                            </p>
                          )}
                        </div>

                        {/* Bottom Metadata */}
                        <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>{formatDate(item.created_at)}</span>
                          {item.word_count ? (
                            <span className="font-medium text-foreground/70">
                              {item.word_count.toLocaleString()} words
                            </span>
                          ) : (
                            <span className="text-primary group-hover:underline">
                              Read transcript →
                            </span>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: number;
  to: string;
  icon: React.ReactNode;
  subtitle: string;
  variant?: "default" | "active" | "warning";
}

function MetricCard({ label, value, to, icon, subtitle, variant = "default" }: MetricCardProps) {
  return (
    <Link to={to} className="group focus:outline-none block h-full">
      <Card
        className={cn(
          "h-full p-3 sm:p-4 transition-all duration-200 hover:shadow-sm flex flex-col justify-between border",
          variant === "warning" && value > 0
            ? "border-amber-500/40 bg-amber-500/5 hover:border-amber-500/70"
            : variant === "active" && value > 0
            ? "border-primary/40 bg-primary/5 hover:border-primary/70"
            : "hover:border-primary/30",
        )}
      >
        <div className="flex items-center justify-between gap-1">
          <span className="text-[11px] sm:text-xs font-semibold text-muted-foreground tracking-tight truncate">
            {label}
          </span>
          <span className="p-1 sm:p-1.5 rounded-lg bg-muted/60 text-foreground group-hover:scale-105 transition-transform duration-150 shrink-0">
            {icon}
          </span>
        </div>

        <div className="mt-2 sm:mt-3 space-y-0.5">
          <p className="font-heading text-lg sm:text-2xl font-bold tracking-tight text-foreground">
            {value.toLocaleString()}
          </p>
          <p className="text-[10px] sm:text-xs text-muted-foreground line-clamp-1">
            {subtitle}
          </p>
        </div>
      </Card>
    </Link>
  );
}
