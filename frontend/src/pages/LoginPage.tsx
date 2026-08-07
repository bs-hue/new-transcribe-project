import { Mic, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ErrorNotice } from "@/components/shared";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { errorMessage, useAuth } from "@/lib/auth";
import type { RegistrationMode } from "@/lib/types";

export function LoginPage() {
  const { user, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Asked of the server rather than assumed, so turning sign-up on is one
  // setting rather than a setting and a frontend rebuild.
  const [mode, setMode] = useState<RegistrationMode>("closed");

  useEffect(() => {
    api
      .registrationMode()
      .then((result) => setMode(result.mode))
      .catch(() => setMode("closed"));
  }, []);

  if (user) return <Navigate to="/" replace />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(errorMessage(err, "Could not sign in."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Mic className="h-6 w-6" />
          </span>
          <div className="space-y-1">
            <CardTitle className="text-xl leading-snug">
              Instagram &amp; YouTube Transcription Agent
            </CardTitle>
            <CardDescription>
              Turn video links into searchable text. Sign in to continue.
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <ErrorNotice message={error} />

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@agency.com"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          {mode === "closed" ? (
            <p className="mt-5 text-xs text-muted-foreground">
              No account? Ask an administrator on your team to create one.
            </p>
          ) : (
            <>
              {/* A labelled divider, so the second button reads as an
                  alternative route rather than a second step of the form. */}
              <div className="my-5 flex items-center gap-3">
                <span className="h-px flex-1 bg-border" />
                <span className="text-xs text-muted-foreground">
                  New here?
                </span>
                <span className="h-px flex-1 bg-border" />
              </div>

              <Button asChild variant="outline" className="w-full">
                <Link to="/register">
                  <UserPlus className="h-4 w-4" />
                  Create an account
                </Link>
              </Button>

              {mode === "approval" ? (
                <p className="mt-3 text-center text-xs text-muted-foreground">
                  An administrator approves new accounts before they can sign in.
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
