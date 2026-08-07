import {
  LayoutDashboard,
  ListChecks,
  LogOut,
  Mic,
  Plus,
  Search,
  Settings,
  Video,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/jobs/new", label: "New job", icon: Plus, end: true },
  { to: "/jobs", label: "Jobs", icon: ListChecks, end: false },
  { to: "/history", label: "History", icon: Video, end: false },
  { to: "/search", label: "Search", icon: Search, end: false },
];

export function Layout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container flex h-16 items-center justify-between gap-6">
          <div className="flex min-w-0 items-center gap-6">
            <NavLink to="/" className="flex shrink-0 items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Mic className="h-4.5 w-4.5" />
              </span>
              {/* The full name is long, so it is shortened rather than
                  truncated mid-word on narrower screens. */}
              <span className="hidden font-semibold leading-tight xl:inline">
                Instagram &amp; YouTube Transcription Agent
              </span>
              <span className="hidden font-semibold lg:inline xl:hidden">
                Transcription Agent
              </span>
            </NavLink>

            <nav className="flex items-center gap-1 overflow-x-auto">
              {LINKS.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden md:inline">{label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Signing out used to be two clicks inside a dropdown, which is one
              click too many for the thing people look for when they want to
              leave. Settings has its own nav entry, so the menu earned nothing. */}
          <div className="flex shrink-0 items-center gap-2">
            <div className="hidden text-right sm:block">
              <p className="max-w-[12rem] truncate text-sm font-medium leading-tight">
                {user?.full_name || user?.email}
              </p>
              {user?.full_name ? (
                <p className="max-w-[12rem] truncate text-xs text-muted-foreground">
                  {user.email}
                </p>
              ) : null}
            </div>

            <Button asChild variant="ghost" size="icon" title="Settings">
              <NavLink to="/settings" aria-label="Settings">
                <Settings className="h-4 w-4" />
              </NavLink>
            </Button>

            <Button variant="outline" size="sm" onClick={signOut}>
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="container py-8">
        <Outlet />
      </main>

      <footer className="container pb-10 text-xs text-muted-foreground">
        Instagram &amp; YouTube Transcription Agent
      </footer>
    </div>
  );
}
