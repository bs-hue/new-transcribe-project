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
        <CardHeader className="space-y-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
            R
          </span>
          <div>
            <CardTitle>Content Research Hub</CardTitle>
            <CardDescription>Sign in to continue.</CardDescription>
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

          <p className="mt-4 text-xs text-muted-foreground">
            {mode === "closed" ? (
              "No account? Ask an administrator on your team to create one."
            ) : (
              <>
                No account?{" "}
                <Link to="/register" className="underline">
                  Create one
                </Link>
                {mode === "approval" ? " — an administrator will approve it." : ""}
              </>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
