import {
  ChevronDown,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Plus,
  Search,
  Settings,
  Video,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
            <NavLink to="/" className="flex shrink-0 items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
                R
              </span>
              <span className="hidden font-semibold lg:inline">Content Research Hub</span>
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

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="shrink-0">
                <span className="hidden max-w-[12rem] truncate sm:inline">
                  {user?.full_name || user?.email}
                </span>
                <ChevronDown />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <NavLink to="/settings" className="cursor-pointer">
                  <span className="flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Settings
                  </span>
                </NavLink>
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={signOut} className="cursor-pointer">
                <span className="flex items-center gap-2">
                  <LogOut className="h-4 w-4" />
                  Sign out
                </span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main className="container py-8">
        <Outlet />
      </main>

      <footer className="container pb-10 text-xs text-muted-foreground">
        Internal research tool · YouTube and Instagram Reels
      </footer>
    </div>
  );
}
