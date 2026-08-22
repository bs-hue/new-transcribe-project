import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ExportMenu } from "@/components/ExportMenu";
import {
  EmptyState,
  ErrorNotice,
  Pagination,
  PlatformBadge,
  Spinner,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatDate, formatDuration, joinParts } from "@/lib/format";
import type { Paged, VideoSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const ALL = "all";

export function HistoryPage() {
  const [page, setPage] = useState<Paged<VideoSummary> | null>(null);
  const [platform, setPlatform] = useState(ALL);
  const [author, setAuthor] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      setPage(
        await api.videos(
          {
            platform: platform === ALL ? undefined : platform,
            author: author || undefined,
            has_transcript: true,
            limit: PAGE_SIZE,
            offset,
          },
          force,
        ),
      );
    } catch (err) {
      setError(errorMessage(err, "Could not load the library."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [platform, author, offset]);

  useEffect(() => {
    // Debounced so typing in the creator box does not fire a request per keystroke.
    const handle = setTimeout(() => void load(false), 250);
    return () => clearTimeout(handle);
  }, [load]);

  function toggle(videoId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(videoId)) next.delete(videoId);
      else next.add(videoId);
      return next;
    });
  }

  const items = page?.items ?? [];
  const total = page?.total ?? 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <header className="flex flex-wrap items-end justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} transcribed video{total === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="h-9 gap-1.5 text-xs font-medium"
            title="Reload latest library data from database"
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-muted-foreground", refreshing && "animate-spin text-primary")} />
            <span>{refreshing ? "Reloading…" : "Reload"}</span>
          </Button>
          <ExportMenu videoIds={[...selected]} label="Export selected" />
        </div>
      </header>

      <div className="flex flex-wrap gap-3">
        <Select
          value={platform}
          onValueChange={(value) => {
            setPlatform(value);
            setOffset(0);
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All platforms</SelectItem>
            <SelectItem value="youtube">YouTube</SelectItem>
            <SelectItem value="instagram">Instagram</SelectItem>
            <SelectItem value="facebook">Meta Ads</SelectItem>
          </SelectContent>
        </Select>

        <Input
          value={author}
          onChange={(event) => {
            setAuthor(event.target.value);
            setOffset(0);
          }}
          placeholder="Filter by creator"
          className="max-w-xs"
        />
      </div>

      <ErrorNotice message={error} />

      {loading && !page ? (
        <Spinner label="Loading…" />
      ) : items.length === 0 ? (
        <EmptyState
          title="Nothing here yet"
          description="Transcribed videos will appear here, ready to read, search and export."
          action={{ to: "/", label: "Add videos" }}
        />
      ) : (
        <Card className="divide-y">
          {items.map((video) => (
            <div key={video.id} className="flex items-start gap-4 p-4">
              <Checkbox
                checked={selected.has(video.id)}
                onCheckedChange={() => toggle(video.id)}
                className="mt-1"
                aria-label={`Select ${video.title ?? "video"}`}
              />
              <Thumbnail src={video.thumbnail_url} alt={video.title ?? "Video"} />
              <div className="min-w-0 flex-1 space-y-1">
                <PlatformBadge platform={video.platform} />
                <Link
                  to={`/history/${video.id}`}
                  className="block truncate text-sm font-medium hover:text-primary"
                >
                  {video.title ?? video.canonical_url}
                </Link>
                <p className="text-xs text-muted-foreground">
                  {joinParts(
                    video.author,
                    formatDuration(video.duration_seconds),
                    `Added ${formatDate(video.created_at)}`,
                  )}
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to={`/history/${video.id}`}>Open</Link>
              </Button>
            </div>
          ))}
        </Card>
      )}

      <Pagination
        total={total}
        limit={PAGE_SIZE}
        offset={offset}
        onChange={setOffset}
        disabled={loading}
      />
    </div>
  );
}
