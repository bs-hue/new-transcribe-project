import {
  ArrowUpRight,
  Compass,
  FileText,
  History,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Mic,
  Plus,
  Search,
  Settings,
  Sparkles,
  Video,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const DESKTOP_LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/jobs", label: "Jobs", icon: ListChecks, end: false },
  { to: "/history", label: "Library", icon: Video, end: false },
  { to: "/search", label: "Search", icon: Search, end: false },
];

const MOBILE_LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/jobs/new", label: "New", icon: Plus, end: true },
  { to: "/jobs", label: "Jobs", icon: ListChecks, end: false },
  { to: "/history", label: "Library", icon: Video, end: false },
  { to: "/search", label: "Search", icon: Search, end: false },
];

export function Layout() {
  const { user, signOut } = useAuth();
  const userInitial = (user?.full_name || user?.email || "U").charAt(0).toUpperCase();
  const userName = (user?.full_name || user?.email || "").split("@")[0];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col antialiased">
      {/* Sticky Top Header */}
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="container flex h-16 items-center justify-between gap-3">
          {/* Logo & Brand */}
          <div className="flex items-center gap-4 lg:gap-7">
            <NavLink to="/" className="flex shrink-0 items-center gap-2.5 sm:gap-3 group focus:outline-none">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-transform duration-200 group-hover:scale-105">
                <Mic className="h-4.5 w-4.5" />
              </span>
              <div className="flex flex-col">
                <span className="font-heading font-semibold text-sm leading-tight tracking-tight sm:text-base">
                  Transcription Hub
                </span>
                <span className="hidden text-[11px] text-muted-foreground font-normal sm:block">
                  YouTube & Instagram AI
                </span>
              </div>
            </NavLink>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1 bg-muted/50 p-1 rounded-xl border border-border/50">
              {DESKTOP_LINKS.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150",
                      isActive
                        ? "bg-background text-foreground shadow-sm font-semibold"
                        : "text-muted-foreground hover:text-foreground hover:bg-background/50",
                    )
                  }
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right Area: Action CTA & Unified User Profile */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Quick new job CTA only on laptop/desktop (>=1024px) where there is plenty of space */}
            <Button asChild size="sm" className="hidden lg:inline-flex h-8 gap-1.5 text-xs shadow-sm font-medium">
              <NavLink to="/jobs/new">
                <Plus className="h-3.5 w-3.5" />
                <span>Transcribe</span>
              </NavLink>
            </Button>

            {/* Unified User & Session Pill */}
            <div className="flex items-center gap-1 bg-muted/50 rounded-xl p-1 border border-border/60">
              <div className="flex items-center gap-2 px-1.5 py-0.5" title={user?.email}>
                <div className="h-6 w-6 rounded-lg bg-primary/10 text-primary border border-primary/20 flex items-center justify-center text-xs font-bold font-heading">
                  {userInitial}
                </div>
                <span className="hidden xl:inline-block max-w-[7rem] truncate text-xs font-medium text-foreground">
                  {userName}
                </span>
              </div>

              {/* Settings Link */}
              <Button asChild variant="ghost" size="icon" className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-background/80" title="Settings">
                <NavLink to="/settings" aria-label="Settings">
                  <Settings className="h-3.5 w-3.5" />
                </NavLink>
              </Button>

              {/* Sign Out Button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={signOut}
                className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/15 transition-colors"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile Sub-Navigation Bar */}
        <div className="flex md:hidden border-t border-border/60 bg-muted/25 px-2 py-1.5 overflow-x-auto">
          <div className="container flex items-center justify-around gap-1">
            {MOBILE_LINKS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex flex-col items-center gap-0.5 rounded-lg px-2 py-1 text-[10px] font-medium transition-colors",
                    isActive
                      ? "text-primary font-semibold"
                      : "text-muted-foreground hover:text-foreground",
                  )
                }
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="container flex-1 py-6 sm:py-8">
        <Outlet />
      </main>

      {/* Clean Modern Footer */}
      <footer className="border-t border-border/60 py-6 text-xs text-muted-foreground bg-muted/20">
        <div className="container flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <div className="flex items-center gap-2 font-medium justify-center sm:justify-start">
            <span className="h-2 w-2 rounded-full bg-success inline-block"></span>
            <span>Transcription Hub · Open Source Local AI</span>
          </div>
          <p className="text-[11px]">
            Fast segment-level transcription for YouTube & Instagram videos
          </p>
        </div>
      </footer>
    </div>
  );
}

