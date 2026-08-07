import { CheckCircle2, CircleAlert, Stethoscope, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { TeamSection } from "@/components/TeamSection";
import { ErrorNotice, Spinner } from "@/components/shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { errorMessage, useAuth } from "@/lib/auth";
import { describeSetting } from "@/lib/format";
import type { SettingsPayload, SystemCheck } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Radix refuses an empty string as a Select value, but "no language chosen" is
 *  genuinely empty on the server. This stands in for it inside the dropdown. */
const AUTO = "__auto__";

export function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your account{isAdmin ? ", how the system behaves, and who can sign in" : ""}.
        </p>
      </header>

      <PasswordSection />
      {isAdmin ? (
        <>
          <SystemSection />
          <SystemCheckSection />
          <TeamSection />
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- my account

function PasswordSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      setDone(true);
    } catch (err) {
      setError(errorMessage(err, "Could not change your password."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">My account</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="max-w-sm space-y-4">
          <ErrorNotice message={error} />
          {done ? (
            <Alert>
              <CheckCircle2 />
              <AlertDescription>Password changed.</AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor="current">Current password</Label>
            <Input
              id="current"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="next">New password</Label>
            <Input
              id="next"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">At least 8 characters.</p>
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? "Changing…" : "Change password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// ------------------------------------------------------------ system settings

function SystemSection() {
  const [data, setData] = useState<SettingsPayload | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const payload = await api.settings();
      setData(payload);
      setDraft(
        Object.fromEntries(
          Object.entries(payload.values).map(([k, v]) => [k, v == null ? "" : String(v)]),
        ),
      );
    } catch (err) {
      setError(errorMessage(err, "Could not load settings."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const payload = await api.updateSettings(draft);
      setData(payload);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err, "Could not save."));
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <Spinner label="Loading settings…" />;

  const changed = Object.entries(draft).some(
    ([key, value]) => String(data.values[key] ?? "") !== value,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">System</CardTitle>
        <p className="text-sm text-muted-foreground">
          Transcription runs locally as <strong>{data.transcription_provider}</strong>,
          processing {data.worker_concurrency} video
          {data.worker_concurrency === 1 ? "" : "s"} at a time.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <ErrorNotice message={error} />
        {saved ? (
          <Alert>
            <CheckCircle2 />
            <AlertDescription>Saved.</AlertDescription>
          </Alert>
        ) : null}

        {data.definitions.map((def) => {
          const plain = describeSetting(draft[def.key] ?? "", def.unit);
          return (
            <div key={def.key} className="max-w-md space-y-1.5">
              <Label htmlFor={def.key}>{def.label}</Label>

              {def.choices ? (
                <Select
                  value={draft[def.key] || AUTO}
                  onValueChange={(value) =>
                    setDraft({ ...draft, [def.key]: value === AUTO ? "" : value })
                  }
                >
                  <SelectTrigger id={def.key}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {def.choices.map((choice) => (
                      <SelectItem key={choice} value={choice || AUTO}>
                        {def.choice_labels?.[choice] ?? choice}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <div className="flex items-center gap-3">
                  <Input
                    id={def.key}
                    type={def.kind === "int" ? "number" : "text"}
                    min={def.minimum ?? undefined}
                    max={def.maximum ?? undefined}
                    value={draft[def.key] ?? ""}
                    placeholder={def.kind === "str" ? "Detect automatically" : undefined}
                    onChange={(e) => setDraft({ ...draft, [def.key]: e.target.value })}
                  />
                  {/* The number as a person would say it, updating as they type. */}
                  {plain ? (
                    <span className="shrink-0 text-sm text-muted-foreground">{plain}</span>
                  ) : null}
                </div>
              )}

              <p className="text-xs text-muted-foreground">
                {def.help} Applies to {def.applies_to}.
              </p>
            </div>
          );
        })}

        <div className="space-y-1.5">
          <Label>Instagram access</Label>
          <p className="text-sm">
            {data.cookies_configured ? (
              <span className="text-success">Configured</span>
            ) : (
              <span className="text-muted-foreground">Not configured</span>
            )}
          </p>
          <p className="text-xs text-muted-foreground">
            Instagram refuses anonymous downloads. Without a cookie file, Instagram links
            fail with a login error. Set <code>COOKIES_FILE</code> and restart — see
            docs/COOKIES.md.
          </p>
        </div>

        <Button onClick={save} disabled={busy || !changed}>
          {busy ? "Saving…" : "Save changes"}
        </Button>
      </CardContent>
    </Card>
  );
}

// -------------------------------------------------------------- system check

function SystemCheckSection() {
  const [result, setResult] = useState<SystemCheck | null>(null);
  const [busy, setBusy] = useState<"quick" | "deep" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(deep: boolean) {
    setBusy(deep ? "deep" : "quick");
    setError(null);
    try {
      setResult(await api.systemCheck(deep));
    } catch (err) {
      setError(errorMessage(err, "The check could not run."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">System check</CardTitle>
        <p className="text-sm text-muted-foreground">
          Confirms this machine can do the job — no terminal needed.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <ErrorNotice message={error} />

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => run(false)} disabled={busy !== null}>
            <Stethoscope />
            {busy === "quick" ? "Checking…" : "Run check"}
          </Button>
          <Button variant="outline" onClick={() => run(true)} disabled={busy !== null}>
            {busy === "deep" ? "Testing transcription…" : "Full check, with transcription"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          The full check downloads the speech model the first time, which can take a few
          minutes, then transcribes a short test clip.
        </p>

        {result ? (
          <div className="divide-y rounded-md border">
            {result.results.map((item) => (
              <div key={item.name} className="flex items-start gap-3 p-3">
                <span className="mt-0.5">
                  {item.ok ? (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  ) : item.warning_only ? (
                    <CircleAlert className="h-4 w-4 text-warning" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="break-words text-xs text-muted-foreground">{item.detail}</p>
                  {item.fix ? (
                    <p
                      className={cn(
                        "mt-1 text-xs",
                        item.warning_only ? "text-warning" : "text-destructive",
                      )}
                    >
                      {item.fix}
                    </p>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
