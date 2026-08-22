import { ArrowRight, History, PlayCircle, RefreshCw, SearchIcon, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ExportMenu } from "@/components/ExportMenu";
import {
  ErrorNotice,
  Pagination,
  PlatformBadge,
  Spinner,
  Thumbnail,
} from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
const ALL = "all";

const POPULAR_TOPICS = [
  "trading",
  "market",
  "loss",
  "video",
  "shailly",
  "strategy",
  "money",
  "investing",
];

function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!query.trim() || !text) return <span>{text}</span>;

  const words = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

  if (words.length === 0) return <span>{text}</span>;

  const regex = new RegExp(`(${words.join("|")})`, "gi");
  const parts = text.split(regex);

  return (
    <span>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark
            key={i}
            className="bg-primary/20 text-primary font-semibold rounded px-0.5"
          >
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </span>
  );
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const initialPlatform = searchParams.get("platform") ?? ALL;

  const [query, setQuery] = useState(initialQuery);
  const [platform, setPlatform] = useState(initialPlatform);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (searchQuery: string, searchPlatform: string, nextOffset = 0) => {
      const trimmed = searchQuery.trim();
      // If both query and platform are empty/all, clear results
      if (!trimmed && searchPlatform === ALL) {
        setResults(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const response = await api.search({
          q: trimmed,
          platform: searchPlatform === ALL ? undefined : searchPlatform,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setResults(response);
        setOffset(nextOffset);
      } catch (err) {
        setError(errorMessage(err, "Search failed."));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // Debounced live search when query or platform changes
  useEffect(() => {
    const handle = setTimeout(() => {
      void run(query, platform, 0);
    }, 300);
    return () => clearTimeout(handle);
  }, [query, platform, run]);

  const handleSuggestionClick = (topic: string) => {
    setQuery(topic);
    void run(topic, platform, 0);
  };

  const handleClear = () => {
    setQuery("");
    if (platform === ALL) {
      setResults(null);
    } else {
      void run("", platform, 0);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <header className="space-y-1">
        <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
          Search Research
        </h1>
        <p className="text-sm text-muted-foreground">
          Find keywords, quotes, or phrases across all transcribed YouTube & Instagram videos.
        </p>
      </header>

      {/* Search Input and Filters */}
      <div className="space-y-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void run(query, platform, 0);
          }}
          className="flex flex-col sm:flex-row gap-2.5"
        >
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search transcript phrases, video titles, creators…"
              className="pl-9 pr-8 h-10 text-sm"
              autoFocus
            />
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
                title="Clear search"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <Select
            value={platform}
            onValueChange={(val) => {
              setPlatform(val);
              void run(query, val, 0);
            }}
          >
            <SelectTrigger className="w-full sm:w-44 h-10 text-xs font-medium">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All Platforms</SelectItem>
              <SelectItem value="youtube">YouTube</SelectItem>
              <SelectItem value="instagram">Instagram</SelectItem>
            </SelectContent>
          </Select>

          <Button type="submit" disabled={loading} className="h-10 px-5 gap-1.5 text-xs font-medium shadow-sm">
            <SearchIcon className="h-3.5 w-3.5" />
            <span>{loading ? "Searching…" : "Search"}</span>
          </Button>
        </form>

        {/* Quick Suggestion Chips */}
        {!results && !query && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1 mr-1">
              <Sparkles className="h-3 w-3 text-primary" />
              <span>Suggested topics:</span>
            </span>
            {POPULAR_TOPICS.map((topic) => (
              <button
                key={topic}
                type="button"
                onClick={() => handleSuggestionClick(topic)}
                className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors border border-border/50"
              >
                {topic}
              </button>
            ))}
          </div>
        )}
      </div>

      <ErrorNotice message={error} />

      {/* Loading Indicator */}
      {loading && !results && (
        <div className="py-12 flex justify-center">
          <Spinner label="Searching transcripts…" />
        </div>
      )}

      {/* Results View */}
      {results && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-border/50">
            <div className="flex items-center gap-2">
              <p className="text-xs sm:text-sm font-medium text-foreground">
                <span className="font-bold">{results.total}</span> result
                {results.total === 1 ? "" : "s"}
                {query.trim() ? ` for “${query.trim()}”` : ""}
                {platform !== ALL ? ` on ${platform}` : ""}
              </p>
              {loading && <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" />}
            </div>

            {results.total > 0 && (
              <ExportMenu query={query.trim() || undefined} label="Export Results" />
            )}
          </div>

          {results.items.length === 0 ? (
            <Card className="p-12 text-center text-muted-foreground border border-dashed bg-muted/20">
              <p className="text-sm font-medium">No matching transcripts found</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                Try searching for different keywords, removing platform filters, or checking spelling.
              </p>
            </Card>
          ) : (
            <Card className="divide-y divide-border/60 overflow-hidden shadow-sm">
              {results.items.map((hit) => (
                <div
                  key={hit.transcript_id}
                  className="flex flex-col sm:flex-row items-start gap-4 p-4 hover:bg-muted/40 transition-colors group"
                >
                  <div className="relative shrink-0">
                    <Thumbnail
                      src={hit.thumbnail_url}
                      alt={hit.title ?? "Video"}
                      className="h-16 w-28 rounded-lg shadow-sm"
                    />
                    {hit.duration_seconds ? (
                      <div className="absolute bottom-1 right-1 rounded bg-black/80 px-1 py-0.5 text-[10px] font-medium text-white">
                        {formatDuration(hit.duration_seconds)}
                      </div>
                    ) : null}
                  </div>

                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <PlatformBadge platform={hit.platform} />
                      <Link
                        to={`/history/${hit.video_id}`}
                        className="truncate text-sm font-semibold hover:text-primary group-hover:text-primary transition-colors flex-1"
                      >
                        <HighlightedText
                          text={hit.title ?? hit.canonical_url ?? "Untitled Video"}
                          query={query}
                        />
                      </Link>
                    </div>

                    <p className="text-xs leading-relaxed text-muted-foreground/90 bg-muted/30 p-2 rounded-md border border-border/40">
                      <HighlightedText text={hit.snippet} query={query} />
                    </p>

                    <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                      <span>
                        {joinParts(
                          hit.author,
                          hit.word_count ? `${hit.word_count.toLocaleString()} words` : null,
                          hit.created_at ? `Added ${formatDate(hit.created_at)}` : null,
                        )}
                      </span>

                      <Link
                        to={`/history/${hit.video_id}`}
                        className="text-primary font-medium hover:underline inline-flex items-center gap-1"
                      >
                        <span>Open Transcript</span>
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </Card>
          )}

          <Pagination
            total={results.total}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={(next) => void run(query, platform, next)}
            disabled={loading}
          />
        </div>
      )}
    </div>
  );
}
