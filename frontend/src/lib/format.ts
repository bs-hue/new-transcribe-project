/** Presentation helpers. Pure functions, no React. */

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`;
}

function plural(value: number, noun: string): string {
  return `${value} ${noun}${value === 1 ? "" : "s"}`;
}

/** "7200 seconds" told nobody anything; "2 hours" does. Used beside settings
 *  inputs, which store raw seconds and bytes because the backend needs them. */
export function describeSetting(raw: string, unit: string | null): string | null {
  const value = Number(raw);
  if (!raw.trim() || Number.isNaN(value) || value < 0) return null;

  if (unit === "bytes") return formatBytes(value);
  if (unit !== "seconds") return null;

  const total = Math.round(value);
  if (total < 60) return plural(total, "second");
  if (total < 3600) return plural(Math.round(total / 60), "minute");

  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);
  return minutes === 0
    ? plural(hours, "hour")
    : `${plural(hours, "hour")} ${plural(minutes, "minute")}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatTimecode(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

const STAGE_LABELS: Record<string, string> = {
  pending: "Waiting",
  fetching_metadata: "Reading video details",
  checking_limits: "Checking limits",
  downloading: "Downloading",
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing",
  storing: "Saving",
  done: "Done",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage.replace(/_/g, " ");
}

export function splitUrls(text: string): string[] {
  return text
    .split(/[\n,\s]+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

export function joinParts(...parts: (string | null | undefined | false)[]): string {
  return parts.filter(Boolean).join(" · ");
}
