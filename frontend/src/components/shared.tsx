import { AlertCircle, ImageOff, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const PLATFORM_LABELS: Record<string, string> = {
  youtube: "YouTube",
  instagram: "Instagram",
};

export function PlatformBadge({ platform }: { platform: string | null | undefined }) {
  if (!platform) return null;
  const variant = platform === "youtube" || platform === "instagram" ? platform : "secondary";
  return <Badge variant={variant}>{PLATFORM_LABELS[platform] ?? platform}</Badge>;
}

const STATUS_VARIANTS = {
  queued: "secondary",
  running: "default",
  completed: "success",
  failed: "destructive",
  cancelled: "secondary",
} as const;

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANTS[status as keyof typeof STATUS_VARIANTS] ?? "secondary";
  return (
    <Badge variant={variant} className="capitalize">
      {status}
    </Badge>
  );
}

export function Thumbnail({
  src,
  alt,
  className,
}: {
  src: string | null | undefined;
  alt: string;
  className?: string;
}) {
  // Platform thumbnail URLs expire and CDNs fail. Without this, a dead URL
  // renders as a broken-image icon with the alt text sprawling across the row.
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  const base = cn("shrink-0 rounded-md object-cover", className ?? "h-16 w-28");
  if (!src || failed) {
    return (
      <div
        className={cn(base, "flex items-center justify-center bg-muted")}
        role="img"
        aria-label={alt}
      >
        <ImageOff className="h-4 w-4 text-muted-foreground" />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className={base}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

export function ErrorNotice({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { to: string; label: string };
}) {
  return (
    <Card className="flex flex-col items-center gap-2 px-6 py-16 text-center">
      <p className="font-medium">{title}</p>
      <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      {action ? (
        <Button asChild className="mt-3">
          <Link to={action.to}>{action.label}</Link>
        </Button>
      ) : null}
    </Card>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
  disabled,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
  disabled?: boolean;
}) {
  if (total <= limit) return null;
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <Button
        variant="outline"
        disabled={disabled || offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        Previous
      </Button>
      <span className="text-muted-foreground">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <Button
        variant="outline"
        disabled={disabled || offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        Next
      </Button>
    </div>
  );
}
