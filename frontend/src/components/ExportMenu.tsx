import { ChevronDown, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import type { ExportFormat } from "@/lib/types";

/** Download control for one transcript or a selection of them.
 *
 *  The format list comes from `/api/meta`, so adding an exporter on the server
 *  adds an option here with no frontend change. */
export function ExportMenu({
  transcriptId,
  transcriptIds,
  videoIds,
  query,
  label = "Export",
  hasSegments = true,
  variant = "outline",
}: {
  transcriptId?: string;
  transcriptIds?: string[];
  videoIds?: string[];
  query?: string;
  label?: string;
  hasSegments?: boolean;
  variant?: "default" | "outline" | "secondary";
}) {
  const [formats, setFormats] = useState<ExportFormat[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .meta()
      .then((meta) => setFormats(meta.export_formats))
      .catch(() => setFormats([]));
  }, []);

  const isBulk = !transcriptId;
  const count = (transcriptIds?.length ?? 0) + (videoIds?.length ?? 0);
  const disabled = isBulk && !query && count === 0;

  async function run(format: ExportFormat, combine = true) {
    setError(null);
    setBusy(`${format.format}:${combine}`);
    try {
      if (transcriptId) {
        await api.exportTranscript(transcriptId, format.format);
      } else {
        await api.bulkExport({
          format: format.format,
          transcript_ids: transcriptIds,
          video_ids: videoIds,
          query,
          combine,
        });
      }
    } catch (err) {
      setError(errorMessage(err, "Export failed."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant={variant} disabled={disabled}>
            <Download />
            {label}
            {isBulk && count > 0 ? ` (${count})` : ""}
            <ChevronDown />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          {/* One transcript has nothing to combine, so it keeps the flat list.
              A selection gets two groups, because "seven reels as one script"
              and "seven files to file away" are both real needs. */}
          <DropdownMenuLabel>
            {isBulk && count > 1 ? `All ${count} in one file` : "Download as"}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {formats.map((format) => {
            const unavailable = format.requires_segments && !hasSegments;
            const noCombined = isBulk && !format.combinable;
            const key = `${format.format}:true`;
            return (
              <DropdownMenuItem
                key={key}
                disabled={unavailable || noCombined || busy !== null}
                onSelect={(event) => {
                  event.preventDefault();
                  void run(format, true);
                }}
                title={
                  unavailable
                    ? "This transcript has no timed segments."
                    : noCombined
                      ? `${format.display_name} timings all start at zero, so a combined file would not play. Use separate files below.`
                      : undefined
                }
              >
                <span>{format.display_name}</span>
                <span className="text-xs uppercase text-muted-foreground">
                  {busy === key ? "…" : format.extension}
                </span>
              </DropdownMenuItem>
            );
          })}

          {isBulk && formats.length > 0 ? (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Separate files (ZIP)</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {formats.map((format) => {
                const unavailable = format.requires_segments && !hasSegments;
                const key = `${format.format}:false`;
                return (
                  <DropdownMenuItem
                    key={key}
                    disabled={unavailable || busy !== null}
                    onSelect={(event) => {
                      event.preventDefault();
                      void run(format, false);
                    }}
                    title={
                      unavailable ? "No selected transcript has timed segments." : undefined
                    }
                  >
                    <span>{format.display_name}</span>
                    <span className="text-xs uppercase text-muted-foreground">
                      {busy === key ? "…" : "zip"}
                    </span>
                  </DropdownMenuItem>
                );
              })}
            </>
          ) : null}

          {formats.length === 0 ? (
            <DropdownMenuItem disabled>No formats available</DropdownMenuItem>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>

      {error ? (
        <p className="absolute right-0 top-full mt-1 whitespace-nowrap text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
