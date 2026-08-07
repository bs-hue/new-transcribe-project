import { UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorNotice, Spinner } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
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
import { formatDate } from "@/lib/format";
import type { User } from "@/lib/types";

export function TeamSection() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await api.users());
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load the team."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleActive(user: User) {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function approve(user: User) {
    try {
      await api.approveUser(user.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove(user: User) {
    if (!confirm(`Remove ${user.email}? Their transcripts stay in the library.`)) return;
    try {
      await api.deleteUser(user.id);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Team</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Who can sign in to the research hub.
          </p>
        </div>
        <Button onClick={() => setShowForm((value) => !value)}>
          <UserPlus />
          {showForm ? "Cancel" : "Add person"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-4">
      <ErrorNotice message={error} />

      {showForm ? (
        <NewUserForm
          onCreated={async () => {
            setShowForm(false);
            await load();
          }}
        />
      ) : null}

      {loading && users.length === 0 ? (
        <Spinner label="Loading…" />
      ) : users.length === 0 ? (
        <EmptyState title="No accounts" description="Add the first team member." />
      ) : (
        <div className="divide-y rounded-md border">
          {users.map((user) => (
            <div key={user.id} className="flex flex-wrap items-center gap-4 p-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {user.full_name || user.email}
                  {user.id === currentUser?.id ? (
                    <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                  ) : null}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {user.email} · joined {formatDate(user.created_at)}
                  {user.last_login_at ? ` · last seen ${formatDate(user.last_login_at)}` : ""}
                </p>
              </div>

              <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                {user.role}
              </Badge>
              {/* Waiting and deactivated are different states and read
                  differently: one is a decision nobody has made yet, the other
                  is a decision somebody made. */}
              {user.approved_at === null ? (
                <Badge variant="warning">waiting for approval</Badge>
              ) : null}
              {user.is_active ? null : <Badge variant="warning">deactivated</Badge>}

              {user.id === currentUser?.id ? null : (
                <div className="flex gap-2">
                  {user.approved_at === null ? (
                    <Button size="sm" onClick={() => approve(user)}>
                      Approve
                    </Button>
                  ) : null}
                  <Button variant="outline" size="sm" onClick={() => toggleActive(user)}>
                    {user.is_active ? "Deactivate" : "Reactivate"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(user)}>
                    Remove
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      </CardContent>
    </Card>
  );
}

function NewUserForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createUser({ email, password, full_name: fullName || undefined, role });
      setEmail("");
      setFullName("");
      setPassword("");
      await onCreated();
    } catch (err) {
      setError(errorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add a team member</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <ErrorNotice message={error} />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="new-email">Email</Label>
              <Input
                id="new-email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="colleague@agency.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-name">Full name</Label>
              <Input
                id="new-name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-password">Temporary password</Label>
              <Input
                id="new-password"
                type="text"
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 8 characters"
              />
              <p className="text-xs text-muted-foreground">
                Share it with them and ask them to change it after signing in.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>Role</Label>
              <Select value={role} onValueChange={(value) => setRole(value as typeof role)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member — can research and export</SelectItem>
                  <SelectItem value="admin">Admin — can also manage accounts</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create account"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
