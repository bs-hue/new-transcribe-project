import {
  AlertCircle,
  FileVideo,
  Globe,
  Loader2,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import React, { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/auth";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = [
  ".mp4",
  ".mov",
  ".mkv",
  ".webm",
  ".avi",
  ".m4v",
  ".wmv",
  ".flv",
  ".mp3",
  ".wav",
  ".m4a",
  ".aac",
  ".ogg",
  ".flac",
];

const LANGUAGE_OPTIONS = [
  { value: "", label: "Auto-detect language" },
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "it", label: "Italian" },
  { value: "ar", label: "Arabic" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "zh", label: "Chinese" },
  { value: "ru", label: "Russian" },
];

interface VideoUploadModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: (jobId: string) => void;
}

export function VideoUploadModal({ open, onClose, onSuccess }: VideoUploadModalProps) {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setFile(null);
    setTitle("");
    setLanguage("");
    setProgress(0);
    setError(null);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleClose = () => {
    if (uploading) return;
    reset();
    onClose();
  };

  const handleFileSelect = (selected: File) => {
    setError(null);
    const ext = "." + (selected.name.split(".").pop()?.toLowerCase() || "");
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(
        `Unsupported file type "${ext}". Supported video & audio: ${ACCEPTED_EXTENSIONS.join(", ")}`
      );
      return;
    }

    // Default max 2 GB
    if (selected.size > 2 * 1024 * 1024 * 1024) {
      setError("File exceeds maximum allowed size of 2 GB.");
      return;
    }

    setFile(selected);
    if (!title) {
      const cleanName = selected.name.substring(0, selected.name.lastIndexOf(".")) || selected.name;
      setTitle(cleanName);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a video or audio file to upload.");
      return;
    }

    setError(null);
    setUploading(true);
    setProgress(0);

    try {
      const res = await api.uploadVideo(file, {
        title: title.trim() || undefined,
        language: language || undefined,
        onProgress: (pct) => setProgress(pct),
      });

      handleClose();
      if (onSuccess) {
        onSuccess(res.job_id);
      } else {
        navigate(`/jobs/${res.job_id}`);
      }
    } catch (err) {
      setError(errorMessage(err, "Failed to upload video. Please check your connection."));
      setUploading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-lg bg-card border border-border/80 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/60 bg-muted/20">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
              <Upload className="h-4.5 w-4.5" />
            </div>
            <div>
              <h2 className="font-heading text-lg font-bold text-foreground">Upload Video</h2>
              <p className="text-xs text-muted-foreground">
                Upload your video or audio file to generate transcripts
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={uploading}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content & Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <Alert variant="destructive" className="py-2.5">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-xs">{error}</AlertDescription>
            </Alert>
          )}

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => {
              const selected = e.target.files?.[0];
              if (selected) handleFileSelect(selected);
            }}
          />

          {/* Drag & Drop Box */}
          {!file ? (
            <div
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "group relative flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200 text-center",
                isDragging
                  ? "border-primary bg-primary/5 scale-[1.01]"
                  : "border-border/80 bg-muted/10 hover:border-primary/50 hover:bg-muted/30"
              )}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-3 group-hover:scale-110 transition-transform">
                <Upload className="h-6 w-6" />
              </div>
              <p className="text-sm font-semibold text-foreground">
                Click to browse or drag and drop video
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                MP4, MOV, MKV, WebM, AVI, MP3, M4A, WAV (up to 2 GB)
              </p>
            </div>
          ) : (
            /* Selected File Chip */
            <div className="flex items-center justify-between p-3.5 rounded-xl border border-primary/30 bg-primary/5">
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                  <FileVideo className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
                </div>
              </div>
              {!uploading && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={reset}
                  className="h-8 text-xs text-muted-foreground hover:text-destructive shrink-0"
                >
                  Change
                </Button>
              )}
            </div>
          )}

          {/* Title & Language Options */}
          {file && (
            <div className="space-y-4 pt-1 animate-in fade-in-50 duration-200">
              <div className="space-y-1.5">
                <Label htmlFor="upload-title" className="text-xs font-semibold">
                  Video Title (optional)
                </Label>
                <Input
                  id="upload-title"
                  type="text"
                  placeholder="Give this video a title for search & library"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={uploading}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                  <Label htmlFor="upload-language" className="text-xs font-semibold">
                    Spoken Language Hint (optional)
                  </Label>
                </div>
                <select
                  id="upload-language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={uploading}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-muted-foreground">
                  Leave on Auto-detect or select a specific language to maximize transcription accuracy.
                </p>
              </div>
            </div>
          )}

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="space-y-2 pt-2 animate-in fade-in duration-150">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 font-medium text-primary">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {progress < 100 ? "Uploading video file..." : "Processing & queueing..."}
                </span>
                <span className="font-mono text-muted-foreground">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border/40">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClose}
              disabled={uploading}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!file || uploading}
              className="gap-1.5 text-xs font-medium shadow-sm"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Uploading…</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Transcribe Video</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
