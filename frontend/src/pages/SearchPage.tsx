import { SearchIcon } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ExportMenu } from "@/components/ExportMenu";
import {
  ErrorNotice,
  Pagination,
  PlatformBadge,
  Spinner,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import type { SearchResponse } from "@/lib/types";

const PAGE_SIZE = 20;
const ALL = "all";

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState(ALL);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(nextOffset = 0) {
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    try {
      setResults(
        await api.search({
          q: trimmed,
          platform: platform === ALL ? undefined : platform,
          limit: PAGE_SIZE,
          offset: nextOffset,
        }),
      );
      setOffset(nextOffset);
    } catch (err) {
      setError(errorMessage(err, "Search failed."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Search research</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Find any phrase across every transcript you have collected.
        </p>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run(0);
        }}
        className="flex flex-wrap gap-3"
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. hook, offer, discount code"
          className="min-w-64 flex-1"
          autoFocus
        />
        <Select value={platform} onValueChange={setPlatform}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All platforms</SelectItem>
            <SelectItem value="youtube">YouTube</SelectItem>
            <SelectItem value="instagram">Instagram</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" disabled={loading || !query.trim()}>
          <SearchIcon />
          {loading ? "Searching…" : "Search"}
        </Button>
      </form>

      <ErrorNotice message={error} />

      {loading && !results ? <Spinner label="Searching…" /> : null}

      {results ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {results.total} result{results.total === 1 ? "" : "s"} for “{results.query}”
            </p>
            {results.total > 0 ? (
              <ExportMenu query={results.query} label="Export all results" />
            ) : null}
          </div>

          {results.items.length === 0 ? (
            <Card className="p-12 text-center text-sm text-muted-foreground">
              Nothing matched. Try a different phrase.
            </Card>
          ) : (
            <Card className="divide-y">
              {results.items.map((hit) => (
                <div key={hit.transcript_id} className="flex items-start gap-4 p-4">
                  <Thumbnail src={hit.thumbnail_url} alt={hit.title ?? "Video"} />
                  <div className="min-w-0 flex-1 space-y-1">
                    <PlatformBadge platform={hit.platform} />
                    <Link
                      to={`/history/${hit.video_id}`}
                      className="block truncate text-sm font-medium hover:text-primary"
                    >
                      {hit.title ?? "Untitled"}
                    </Link>
                    <p className="text-sm leading-6 text-muted-foreground">{hit.snippet}</p>
                    <p className="text-xs text-muted-foreground">
                      {joinParts(
                        hit.author,
                        formatDuration(hit.duration_seconds),
                        hit.created_at ? `Added ${formatDate(hit.created_at)}` : null,
                      )}
                    </p>
                  </div>
                </div>
              ))}
            </Card>
          )}

          <Pagination
            total={results.total}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={(next) => void run(next)}
            disabled={loading}
          />
        </>
      ) : null}
    </div>
  );
}
