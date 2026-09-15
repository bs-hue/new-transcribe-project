import { ArrowLeft, CheckCircle2, KeyRound, Mail } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
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
import { errorMessage } from "@/lib/auth";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(errorMessage(err, "Could not process password reset request."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <Card className="w-full max-w-sm shadow-md border-border/80">
        <CardHeader className="space-y-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
            {sent ? <CheckCircle2 className="h-6 w-6 text-emerald-500" /> : <KeyRound className="h-6 w-6" />}
          </span>
          <div className="space-y-1">
            <CardTitle className="text-xl font-bold tracking-tight">
              {sent ? "Reset Link Sent" : "Forgot Password?"}
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm">
              {sent
                ? `We've sent a password reset link to your email address.`
                : "Enter your registered email address and we'll send you a link to reset your password."}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {sent ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground space-y-1.5 border border-border/40">
                <p className="flex items-center gap-1.5 font-medium text-foreground">
                  <Mail className="h-3.5 w-3.5 text-primary" />
                  Sent to: <span className="text-primary">{email}</span>
                </p>
                <p>
                  Please check your inbox and click the reset link to choose a new password. The link will expire in 30 minutes.
                </p>
              </div>

              <Button asChild className="w-full" variant="default">
                <Link to="/login">
                  <ArrowLeft className="h-4 w-4 mr-1.5" />
                  Return to Sign In
                </Link>
              </Button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setSent(false)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors underline"
                >
                  Didn't receive the email? Try again
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <ErrorNotice message={error} />

              <div className="space-y-1.5">
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@agency.com"
                />
              </div>

              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Sending link…" : "Send Reset Link"}
              </Button>

              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Back to Sign In
                </Link>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
