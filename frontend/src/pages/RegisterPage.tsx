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

/** Public sign-up.
 *
 *  What happens after submitting depends on the server: with approval required
 *  the account waits for an administrator, so the page says so rather than
 *  bouncing to a sign-in that would fail. With open registration it signs the
 *  person straight in, because making them retype what they just typed is
 *  ceremony. */
export function RegisterPage() {
  const { user, signIn } = useAuth();
  const [mode, setMode] = useState<RegistrationMode | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    api
      .registrationMode()
      .then((result) => setMode(result.mode))
      .catch(() => setMode("closed"));
  }, []);

  if (user) return <Navigate to="/" replace />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await api.register({
        email,
        password,
        full_name: fullName.trim() || undefined,
      });
      if (mode === "open") {
        await signIn(email, password);
      } else {
        setSubmitted(true);
      }
    } catch (err) {
      setError(errorMessage(err, "Could not create the account."));
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
            <CardTitle>Create an account</CardTitle>
            <CardDescription>
              {mode === "approval"
                ? "An administrator reviews new accounts before they can sign in."
                : "Sign up to start collecting transcripts."}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          {submitted ? (
            <div className="space-y-4">
              <p className="text-sm">
                Thanks — your account has been created and is waiting for an
                administrator to approve it. You will be able to sign in once
                they do.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">Back to sign in</Link>
              </Button>
            </div>
          ) : mode === "closed" ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                This service is invitation-only. Ask an administrator to create
                an account for you.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">Back to sign in</Link>
              </Button>
            </div>
          ) : (
            <>
              <form onSubmit={submit} className="space-y-4">
                <ErrorNotice message={error} />

                <div className="space-y-1.5">
                  <Label htmlFor="full_name">Your name</Label>
                  <Input
                    id="full_name"
                    autoComplete="name"
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    placeholder="Optional"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    At least 8 characters.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="confirm">Confirm password</Label>
                  <Input
                    id="confirm"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                  />
                </div>

                <Button type="submit" className="w-full" disabled={busy || mode === null}>
                  {busy ? "Creating…" : "Create account"}
                </Button>
              </form>

              <p className="mt-4 text-xs text-muted-foreground">
                Already have an account?{" "}
                <Link to="/login" className="underline">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
